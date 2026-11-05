"""Stand-in for the Dynatrace MCP server, used only for testing the proxy."""
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("fake-dynatrace")


@mcp.tool()
def execute_dql(query: str) -> str:
    """Pretend to run a DQL query."""
    return f"rows for: {query}"


if __name__ == "__main__":
    mcp.run("stdio")