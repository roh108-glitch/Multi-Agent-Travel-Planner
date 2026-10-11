from typing import Any, List, Dict
from langchain_mcp_adapters.client import MultiServerMCPClient
from ..app.config import settings


def get_mcp_server_config() -> dict[str, Any]:
    """Generates configuration dictionary for local and remote MCP servers."""
    return {
        # Local Python FastMCP Servers (Stdio)
        "budget": {
            "command": settings.MCP_PYTHON_PATH,
            "args": [settings.BUDGET_SERVER_PATH],
            "transport": "stdio",
        },
        "accommodation": {
            "command": settings.MCP_PYTHON_PATH,
            "args": [settings.ACCOMMODATION_SERVER_PATH],
            "transport": "stdio",
        },
        "attractions": {
            "command": settings.MCP_PYTHON_PATH,
            "args": [settings.ATTRACTIONS_SERVER_PATH],
            "transport": "stdio",
        },
        "weather": {
            "command": settings.MCP_PYTHON_PATH,
            "args": [settings.WEATHER_SERVER_PATH],
            "transport": "stdio",
        },
        "transport": {
            "command": settings.MCP_PYTHON_PATH,
            "args": [settings.TRANSPORT_SERVER_PATH],
            "transport": "stdio",
        },
        # Remote Tavily MCP Server via NPX
        "tavily": {
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={settings.TAVILY_API_KEY}",
            "transport": "streamable_http"
        }
    }

async def get_agent_tools() -> Dict[str, List[Any]]:
    """Loads MCP tools categorized by agent without blocking on a long-lived context manager."""
    server_config = get_mcp_server_config()

    # Instantiate the client directly (no async with needed)
    client = MultiServerMCPClient(server_config)

    # 1. Fetch general search tools from Tavily
    tavily_tools = await client.get_tools(server_name="tavily")

    agent_server_map = {
        "budget_expert": "budget",
        "accommodation_expert": "accommodation",
        "attractions_expert": "attractions",
        "weather_expert": "weather",
        "transportation_expert": "transport",
    }

    agent_tools: Dict[str, List[Any]] = {}

    for agent_name, server_name in agent_server_map.items():
        specific_tools = await client.get_tools(server_name=server_name)
        agent_tools[agent_name] = specific_tools + tavily_tools

    return agent_tools



