"""Allow ``python -m src.mcp_server`` to start the MCP server."""

from .server import main

if __name__ == "__main__":
    raise SystemExit(main())
