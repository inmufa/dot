"""MCP server status DTO served under /v1/mcp/servers."""

from typing import Literal

from pydantic import BaseModel

McpTransport = Literal["stdio", "http", "sse"]
McpStatus = Literal["connecting", "connected", "failed", "needs_trust", "stopped"]


class McpServerInfo(BaseModel):
    name: str
    transport: McpTransport
    scope: Literal["user", "project"]
    status: McpStatus
    tool_count: int = 0
    trusted: bool
    error: str | None = None
