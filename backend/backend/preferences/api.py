"""GET/PUT /v1/preferences: reply tone and emoji use."""

from fastapi import Request

from backend.core.api.auth import protected_router
from backend.preferences.service import PreferencesService, ReplyStyle

router = protected_router(prefix="/v1", tags=["preferences"])


def service(request: Request) -> PreferencesService:
    return request.app.state.preferences


@router.get("/preferences")
async def get_preferences(request: Request) -> ReplyStyle:
    return service(request).style


@router.put("/preferences")
async def put_preferences(request: Request, body: ReplyStyle) -> ReplyStyle:
    return service(request).save(body)
