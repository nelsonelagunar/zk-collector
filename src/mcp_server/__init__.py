"""MCP (Model Context Protocol) server for zk-collector (MYK-408).

Exposes read-only tools over the existing REST/JSON endpoints of the
WebGUI (attendance stats, punches, devices, employees) so AI agents can
query the platform. The server authenticates every API call with a token
from the environment and never exposes secrets to the model.

Install with the optional extra: ``pip install zk-collector[mcp]``.
Run with: ``zk-collector-mcp`` (stdio, default) or ``python -m src.mcp_server``.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
