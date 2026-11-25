"""Files list, preview and tree (F4)."""

from typing import Annotated

from dot_contracts.ui.files import FileInfo, TreeEntry
from fastapi import Query, Request, Response

from backend.core.api.auth import protected_router
from backend.sessions.services.session_service import SessionService
from backend.sessions.services.workspace.files import FilesService
from backend.sessions.services.workspace.preview import preview_response

router = protected_router(prefix="/v1", tags=["files"])


def svc(request: Request) -> FilesService:
    return request.app.state.files


@router.get("/sessions/{session_id}/files")
async def session_files(request: Request, session_id: str) -> list[FileInfo]:
    row = await SessionService(request.app.state.sessions).get(session_id)
    return await svc(request).session_files(row.public_id, row.id, row.created_at)


@router.get("/files/content")
async def file_content(
    request: Request,
    path: Annotated[str, Query(min_length=1, max_length=1000)],
    render: Annotated[int, Query(ge=0, le=1)] = 0,
) -> Response:
    data, real = await svc(request).content("preview", path)
    return preview_response(data, real, render=bool(render))


@router.get("/files/tree")
async def file_tree(
    request: Request,
    path: Annotated[str | None, Query(max_length=1000)] = None,
    depth: Annotated[int, Query(ge=1, le=4)] = 1,
) -> list[TreeEntry]:
    return await svc(request).tree("preview", path, depth)
