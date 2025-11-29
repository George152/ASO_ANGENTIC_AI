"""
AI filesystem administrator wired for Google ADK, LiteLLM, and MCP tools.
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    SseConnectionParams,
)
from mcp import StdioServerParameters

# warnings suppression----------------------------------

# Suppress deprecation warnings from httpx and aiohttp
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="aiohttp")
# Suppress ALL warnings from google.genai.types (including Pydantic custom classes)
warnings.filterwarnings("ignore", module="google.genai.types")


# Model configuration ----------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MCP_STDIO_TIMEOUT = float(os.getenv("MCP_STDIO_TIMEOUT", "10.0"))

# Configuration from environment (with defaults for local dev)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN")

print(f"DEBUG: OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")

model_llama = LiteLlm(
    model="ollama_chat/llama3.2:latest",
    base_url=OLLAMA_BASE_URL,
    stream=True,
    # temperature=0, # Force deterministic output
)

def _build_connection_params() -> StdioConnectionParams | SseConnectionParams:
    """Prepare the connection configuration used by ADK."""
    
    # If MCP_SERVER_URL is set, use SSE (e.g. in Docker)
    if MCP_SERVER_URL:
        return SseConnectionParams(
            url=MCP_SERVER_URL,
            headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"} if MCP_AUTH_TOKEN else None,
            timeout=MCP_STDIO_TIMEOUT
        )

    # Otherwise fallback to local Stdio (for local dev)
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-u", "-m", "basic_agent.mcp_file"],
        cwd=str(PROJECT_ROOT),
        env=dict(os.environ),
    )
    return StdioConnectionParams(server_params=server_params, timeout=MCP_STDIO_TIMEOUT)


# Shared toolset for the agent.
filesystem_toolset = McpToolset(connection_params=_build_connection_params())



SYSTEM_INSTRUCTION = """
You are an AI system administrator responsible for managing files and directories on a computer system.
You are using google adk, ollama, litellm and fastmcp.
All file/directory paths in tool calls are relative to this base directory unless specified as absolute.

CRITICAL INSTRUCTION:
The tools you use are designed to return NATURAL LANGUAGE summaries of their results.
You should rely on these summaries to formulate your response to the user.
Do NOT try to parse the raw data if the summary is sufficient.

Workflow:
1. Explain briefly what you are about to inspect, then call the single best tool.
2. The tool will return a natural language description of the result. READ IT CAREFULLY.
3. Use that description to answer the user. Do NOT simply echo the tool output, but synthesize it into a helpful response.
4. Only call the same tool again if you genuinely need additional information that was not already returned.

Available tools (call EXACTLY as shown):
- list_directory(dir_path=".") - list contents
- get_file_content(file_path="path/to/file.txt") - read file
- get_file_info(file_path="path") - metadata
- search_files(pattern="*.txt", dir_path=".") - find files
- get_directory_tree(dir_path=".", max_depth=3) - visualize structure
- get_disk_usage(dir_path=".") - calculate size
- find_large_files(dir_path=".", min_size_mb=1.0, limit=10) - largest files
- count_files_by_extension(dir_path=".") - group by extension

MANDATORY OUTPUT FORMAT:
- You must ALWAYS answer in plain English sentences.
- You must NEVER output JSON, XML, or code blocks in your final response unless explicitly asked for code.
- If a tool returns a list of files, summarize it (e.g., "I found 5 files, including a.txt and b.txt").
"""

print(f"DEBUG: Loaded SYSTEM_INSTRUCTION length: {len(SYSTEM_INSTRUCTION)}")

# The ADK-compatible agent definition. This object is loaded by `google-adk cli/web`.
root_agent = LlmAgent(
    name="SysAdmin_Agent",
    model=model_llama,
    description="AI system administrator managing filesystem.",
    instruction=SYSTEM_INSTRUCTION,
    tools=[filesystem_toolset],
)

__all__ = ["root_agent"]
