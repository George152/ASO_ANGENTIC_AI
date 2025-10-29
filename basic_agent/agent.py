"""
Agent AI pentru administrarea sistemului de fișiere folosind ADK și MCP.
"""
import litellm
from typing import Any, Dict, List
from pathlib import Path
import json
import sys
import asyncio
from fastmcp.client.transports import MCPConfigTransport
from fastmcp import Client
from google.adk.agents import LlmAgent

# warnings suppression----------------------------------

import warnings
# Suppress deprecation warnings from httpx and aiohttp
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="aiohttp")
# Suppress ALL warnings from google.genai.types (including Pydantic custom classes)
warnings.filterwarnings("ignore", module="google.genai.types")

# model configuration ----------------------------------

# Modelul folosit de LiteLLM (Ollama)
LITELLM_MODEL = "ollama/llama3.2:latest"

# Configurare model pentru ADK (rămâne ca metadată)
MODEL_NAME = "litellm/ollama/llama3.2:latest"

# Clasă wrapper pentru a integra fastmcp.Client ca tool provider


class MCPToolWrapper:
    def __init__(self, client: Client):
        self.client = client
        self._tools = None  # cache tool defs

    async def list_tools(self):
        if self._tools is None:
            async with self.client:
                self._tools = await self.client.list_tools()
        return self._tools

    async def call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        async with self.client:
            return await self.client.call_tool(tool_name, arguments)

    async def to_openai_tools(self) -> List[Dict[str, Any]]:
        """
        Transformă tool-urile MCP în format OpenAI tools pentru function calling.
        Acceptă atât obiectele Tool (fastmcp) cât și dict-urile.
        """
        tools = await self.list_tools()
        out: List[Dict[str, Any]] = []

        for t in tools:
            if isinstance(t, dict):
                name = t.get("name")
                description = t.get("description", "")
                schema = t.get("input_schema") or t.get("inputSchema") or {
                    "type": "object", "properties": {}}
            else:
                # Obiect fastmcp Tool
                name = getattr(t, "name", None)
                description = getattr(t, "description", "") or ""
                schema = getattr(t, "input_schema", None) or getattr(
                    t, "inputSchema", None) or {"type": "object", "properties": {}}

            if not isinstance(schema, dict):
                schema = {"type": "object", "properties": {}}

            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": schema,
                    },
                }
            )
        return out


# Config MCP pentru stdio -> pornește serverul basic_agent.mcp_file
MCP_CONFIG = {
    "mcpServers": {
        "filesystem_admin": {
            "command": sys.executable,                     # Python din venv
            # rulează serverul ca modul
            "args": ["-u", "-m", "basic_agent.mcp_file"],
            # IMPORTANT: cwd = rădăcina proiectului, NU basic_agent/
            "cwd": str(Path(__file__).resolve().parents[1]),
            "env": {},
        }
    }
}

# Client fastmcp pe baza config-ului
mcp_client = Client(MCPConfigTransport(MCP_CONFIG))
mcp_tool = MCPToolWrapper(mcp_client)

# Definește agentul (ADK ca metadată/config)
agent = LlmAgent(
    name="SysAdmin_Agent",
    model=MODEL_NAME,
    description="Agent AI care administrează sistemul de fișiere și răspunde la întrebări despre directorul administrat.",
    instruction="""
    Ești un administrator de sistem inteligent și prietenos.
    Folosește tool-urile MCP când ai nevoie de informații din sistemul de fișiere.
    Răspunde în limba engleza.
    """,
    # tools=[mcp_tool],  # <- eliminat: nu este BaseTool/BaseToolset
)


async def run_one_turn(user_input: str) -> str:
    """
    Un singur turn de conversație cu function-calling:
    - trimite mesajul + tool-urile către LLM
    - dacă LLM cere tool_call(s), le execută prin fastmcp
    - re-trimite contextul + rezultate pentru răspunsul final
    """
    # 1) Construiește tool-urile pentru LLM
    openai_tools = await mcp_tool.to_openai_tools()

    # 2) Pornește conversația
    messages = [
        {"role": "system", "content": agent.instruction or ""},
        {"role": "user", "content": user_input},
    ]

    # 3) Primul apel la LLM (poate cere tool-calls)
    first = await litellm.acompletion(
        model=LITELLM_MODEL,
        messages=messages,
        tools=openai_tools,
        tool_choice="auto",
    )
    # Normalizează mesajul și tool_calls (pot fi obiecte)
    msg = first.choices[0].message
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content", "")

    tool_calls_raw = getattr(msg, "tool_calls", None)
    if tool_calls_raw is None and isinstance(msg, dict):
        tool_calls_raw = msg.get("tool_calls")

    # Funcții helper pentru extragere sigură
    def _tc_id(tc):
        return getattr(tc, "id", None) if not isinstance(tc, dict) else tc.get("id")

    def _tc_function(tc):
        f = getattr(tc, "function", None) if not isinstance(
            tc, dict) else tc.get("function")
        if f is None:
            return None, {}
        name = getattr(f, "name", None) if not isinstance(
            f, dict) else f.get("name")
        raw_args = getattr(f, "arguments", "{}") if not isinstance(
            f, dict) else f.get("arguments", "{}")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        return name, args

    # Dacă nu sunt tool-calls -> răspuns direct
    if not tool_calls_raw:
        return content or ""

    # 4) Execută tool-urile cerute de model
    normalized_tool_calls = []
    for tc in tool_calls_raw:
        func_name, args = _tc_function(tc)
        if not func_name:
            continue
        result_raw = await mcp_tool.call(func_name, args)

        # Extrage conținutul serializabil din CallToolResult
        if hasattr(result_raw, "content"):
            # FastMCP CallToolResult are .content (list of TextContent/ImageContent/etc)
            content_items = result_raw.content
            if isinstance(content_items, list):
                # Extrage text din fiecare item
                result_str = "\n".join(
                    getattr(item, "text", str(item)) if hasattr(
                        item, "text") else str(item)
                    for item in content_items
                )
            else:
                result_str = str(content_items)
        else:
            result_str = str(result_raw)

        # Construiește tool_call dict (format OpenAI)
        normalized = {
            "id": _tc_id(tc) or "",
            "type": "function",
            "function": {
                "name": func_name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        }
        normalized_tool_calls.append(normalized)
        # Adaugă în context: tool call + rezultatul tool-ului
        messages.append(
            {"role": "assistant", "content": content or "", "tool_calls": [normalized]})
        messages.append(
            {
                "role": "tool",
                "tool_call_id": normalized["id"],
                "name": func_name,
                # <- folosește stringul extras, NU json.dumps(result_raw)
                "content": result_str,
            }
        )

    # 5) Al doilea apel pentru răspunsul final, după tool results
    final = await litellm.acompletion(
        model=LITELLM_MODEL,
        messages=messages,
    )
    final_msg = final.choices[0].message
    return getattr(final_msg, "content", None) or (final_msg.get("content") if isinstance(final_msg, dict) else "") or ""


async def main():
    print("=" * 60)
    print("Agent AI - Administrator de Sistem (LiteLLM + FastMCP)")
    print("=" * 60)
    print(f"Model LiteLLM: {LITELLM_MODEL}")
    # afișează tool-urile disponibile din MCP pentru debug
    try:
        tools = await mcp_tool.list_tools()
        # EVITĂ t.get(...) pe obiecte; folosește isinstance
        tool_names = [t["name"] if isinstance(
            t, dict) else getattr(t, "name", None) for t in tools]
        print(f"Tool-uri MCP detectate: {tool_names}")
    except Exception as e:
        print(f"Nu s-au putut încărca tool-urile MCP: {e}")
    print("Scrie 'exit' sau 'quit' pentru a ieși")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("Tu: ").strip()
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nLa revedere!")
                break
            if not user_input:
                continue

            print("\nAgent: ", end="", flush=True)
            response = await run_one_turn(user_input)
            print(response)
            print()
        except KeyboardInterrupt:
            print("\n\nÎntrerupt de utilizator. La revedere!")
            break
        except Exception as e:
            print(f"\nEroare: {e}")
            print("Încearcă din nou.\n")


if __name__ == "__main__":
    asyncio.run(main())
