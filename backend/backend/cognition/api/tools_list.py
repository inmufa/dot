"""GET /v1/tools: every registered tool (core and deferred) with its flags."""

from dot_contracts.tools import ToolInfo
from fastapi import Request

from backend.core.api.auth import protected_router

router = protected_router(prefix="/v1", tags=["tools"])


@router.get("/tools")
async def list_tools(request: Request) -> list[ToolInfo]:
    registry = request.app.state.agent.registry
    return [
        ToolInfo(
            name=d.name,
            description=d.description,
            deferred=d.deferred,
            mutating=d.mutating,
            source="mcp" if d.name.startswith("mcp__") else "builtin",
            input_schema=d.input_schema,
        )
        for d in registry.definitions()
    ]
