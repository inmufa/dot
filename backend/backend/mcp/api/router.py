"""GET /v1/mcp/servers, POST .../reconnect, POST .../trust."""

from dot_contracts.mcp import McpServerInfo
from fastapi import Request

from backend.core.api.auth import protected_router

router = protected_router(prefix="/v1/mcp", tags=["mcp"])


@router.get("/servers")
async def list_servers(request: Request) -> list[McpServerInfo]:
    mcp = request.app.state.mcp
    await mcp.reconcile()
    return mcp.infos()


@router.post("/servers/{name}/reconnect")
async def reconnect(request: Request, name: str) -> McpServerInfo:
    return await request.app.state.mcp.reconnect(name)


@router.post("/servers/{name}/trust")
async def trust(request: Request, name: str) -> McpServerInfo:
    return await request.app.state.mcp.trust(name)
