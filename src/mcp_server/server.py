"""FastMCP server wiring for zk-collector (MYK-408).

Transport: stdio by default (no port is opened at all — the MCP client
spawns this process). HTTP (streamable) is opt-in via ZK_COLLECTOR_MCP_HTTP=1
and binds to 127.0.0.1 by default so nothing is reachable from the network;
non-loopback binds are rejected unless ZK_COLLECTOR_MCP_ALLOW_REMOTE_BIND=1.
The collector port 4370 and the WebGUI are never touched by this server.
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from .client import ZkCollectorClient
from .config import ConfigError, MCPConfig
from .tools import build_tools

SERVER_NAME = "zk-collector"
INSTRUCTIONS = (
    "Read-only access to a zk-collector attendance platform. Use these tools "
    "to query attendance KPIs, raw punches, devices and employees. All tools "
    "are read-only; credentials are handled by the server and never exposed."
)


def build_server(config: MCPConfig) -> FastMCP:
    """Create the FastMCP instance with all tools registered."""
    mcp = FastMCP(
        SERVER_NAME,
        instructions=INSTRUCTIONS,
        host=config.http_host,
        port=config.http_port,
    )
    client = ZkCollectorClient(config)
    for name, tool_fn in build_tools(client).items():
        mcp.tool(name=name)(tool_fn)
    return mcp


def main() -> int:
    """Console entry point (``zk-collector-mcp``)."""
    try:
        config = MCPConfig.from_env()
    except ConfigError as exc:
        print(f"zk-collector-mcp: configuration error: {exc}", file=sys.stderr)
        return 2

    server = build_server(config)
    if config.http_enabled:
        server.run(transport="streamable-http")
    else:
        server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
