# System Admin Agent (Google ADK)

This agent uses google.adk with the built-in LiteLlm model wrapper and the MCP toolset. When the agent is loaded through the Google ADK CLI or Web UI, it automatically spins up the local MCP server defined in basic_agent.mcp_file and limits its access to the folder specified by FILESYSTEM_ADMIN_ROOT in .env.

## Configure

1. Install dependencies: pip install -r requirements.txt. Activate the virtual environment if needed.
2. Update basic_agent/.env:
   - FILESYSTEM_ADMIN_ROOT must point to the folder you administrate (default already set).
   - ADK_LITELLM_MODEL selects the LiteLlm target (ollama/llama3.2:latest).
   - LITELLM_API_BASE / LITELLM_OLLAMA_API_BASE should match your running Ollama endpoint.
3. Make sure the folder defined in FILESYSTEM_ADMIN_ROOT exists and that you want to expose its content to the agent.

## Run the lightweight CLI (recommended)

If you want the fastest turnaround, use the manual CLI that ships with this repo:

```powershell
python -m basic_agent.manual_cli
```

It talks directly to LiteLLM + FastMCP, avoids the ADK planner, and prevents duplicate tool calls.

## Run with the Google ADK CLI/Web

You can still use the official ADK interfaces:

```powershell
google-adk cli basic_agent
```

or

```powershell
google-adk web basic_agent
```

Both commands pick up `.env`, spawn the MCP server, and present the agent in the ADK CLI/Web UI.

## Notes

- If you change the administered folder, update FILESYSTEM_ADMIN_ROOT and restart the CLI/Web server.
- To switch models, update ADK_LITELLM_MODEL (for example ollama/qwen2.5:14b).
- The MCP server logs to stderr when it starts; check the terminal running google-adk ... if you need to troubleshoot.
