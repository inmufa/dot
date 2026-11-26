"""Inline chat images: GET /v1/media?src=<http(s) URL | workspace path>."""

from typing import Annotated

from fastapi import Query, Request, Response

from backend.core.api.auth import protected_router
from backend.sessions.services.workspace.media import MediaService

router = protected_router(prefix="/v1", tags=["media"])


def svc(request: Request) -> MediaService:
    return request.app.state.media


@router.get("/media")
async def media(
    request: Request, src: Annotated[str, Query(min_length=1, max_length=4096)]
) -> Response:
    item = await svc(request).load("preview", src)
    return Response(
        item.data,
        media_type=item.mime,
        headers={
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )
