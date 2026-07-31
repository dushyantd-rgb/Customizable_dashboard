from mcp.server.fastmcp import FastMCP


def register_tools(_server: FastMCP) -> None:
    """Register MCP tools in later phases.

    Phase 1 intentionally leaves the allowlist empty.
    """
