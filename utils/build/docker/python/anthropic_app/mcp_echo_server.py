"""Minimal stdio MCP server with an echo tool, spawned by the /mcp/create endpoint."""

from mcp.server.fastmcp import FastMCP


server = FastMCP("echo")


@server.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return text


if __name__ == "__main__":
    server.run()
