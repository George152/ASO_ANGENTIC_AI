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
DEFAULT_LITELLM_MODEL = os.getenv(
    "ADK_LITELLM_MODEL", "ollama_chat/gpt-oss:20b")
MCP_STDIO_TIMEOUT = float(os.getenv("MCP_STDIO_TIMEOUT", "10.0"))

model_llama = LiteLlm(
    model="ollama_chat/llama3.2:latest",
    base_url="http://localhost:11434",
    stream=True,
)


def _build_stdio_params() -> StdioConnectionParams:
    """Prepare the stdio configuration used by ADK."""

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-u", "-m", "basic_agent.mcp_file"],
        cwd=str(PROJECT_ROOT),
        env=dict(os.environ),
    )
    return StdioConnectionParams(server_params=server_params, timeout=MCP_STDIO_TIMEOUT)


# Shared toolset for the agent.
filesystem_toolset = McpToolset(connection_params=_build_stdio_params())


SYSTEM_INSTRUCTION = """
You are an AI system administrator responsible for managing files and directories on a computer system.
You are using google adk, ollama, litellm and fastmcp.
All file/directory paths in tool calls are relative to this base directory unless specified as absolute.

Workflow:
1. Explain briefly what you are about to inspect, then call the single best tool.
2. After a tool responds, read its structured content (summary/data) and convert it to natural language. Never echo raw JSON back to the user.
3. Only call the same tool again if you genuinely need additional information that was not already returned.

Available tools (call EXACTLY as shown):
- list_directory(dir_path=".") - list contents
- get_file_content(file_path="path/to/file.txt") - read file
- get_file_info(file_path="path") - metadata
- search_files(pattern="*.txt", dir_path=".") - find files
- get_directory_tree(dir_path=".", max_depth=3) - visualize structure
- get_disk_usage(dir_path=".") - calculate size
- find_large_files(dir_path=".", min_size_mb=1.0, limit=10) - largest files
- count_files_by_extension(dir_path=".") - group by extension

Final responses must be concise natural language such as:
"The administered folder currently contains the single file secret.txt."
"""

# The ADK-compatible agent definition. This object is loaded by `google-adk cli/web`.
root_agent = LlmAgent(
    name="SysAdmin_Agent",
    model=model_llama,
    description="AI system administrator managing filesystem.",
    instruction=SYSTEM_INSTRUCTION,
    tools=[filesystem_toolset],
)

__all__ = ["root_agent"]
