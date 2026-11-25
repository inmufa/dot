"""Attachment routes (F3)."""

from dot_contracts.ui.files import Attachment
from fastapi import Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import UploadFile as FormFile

from backend.core.api.auth import protected_router
from backend.core.exceptions import DomainException
from backend.sessions.services.session_service import SessionService
from backend.sessions.services.workspace.attachments import (
    TOO_LARGE,
    TOO_MANY,
    AttachmentService,
    Upload,
    to_dto,
)

router = protected_router(prefix="/v1", tags=["attachments"])


def svc(request: Request) -> AttachmentService:
    return request.app.state.attachments


async def _read(file: UploadFile, cap: int) -> bytes:
    data = await file.read(cap + 1)
    if len(data) > cap:
        raise DomainException(TOO_LARGE)
    return data


@router.post("/sessions/{session_id}/attachments", status_code=201)
async def upload(request: Request, session_id: str) -> list[Attachment]:
    row = await SessionService(request.app.state.sessions).get(session_id)
    service = svc(request)
    form = await request.form(max_files=service.max_files + 1, max_fields=10)
    files = [f for f in form.getlist("files") if isinstance(f, FormFile)]
    if not files:
        raise RequestValidationError([])
    if len(files) > service.max_files:
        raise DomainException(TOO_MANY)
    uploads = [
        Upload(f.filename or "file", await _read(f, service.max_bytes)) for f in files
    ]
    await form.close()
    return [to_dto(r) for r in await service.save(row.public_id, uploads)]


@router.get("/sessions/{session_id}/attachments")
async def list_attachments(request: Request, session_id: str) -> list[Attachment]:
    row = await SessionService(request.app.state.sessions).get(session_id)
    return [to_dto(r) for r in await svc(request).list(row.public_id)]


@router.get("/attachments/{attachment_id}/content")
async def content(request: Request, attachment_id: str) -> Response:
    service = svc(request)
    row = await service.get(attachment_id)
    data = await service.content(row)
    inline = row.kind == "image"
    headers = {
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Content-Disposition": f"{'inline' if inline else 'attachment'}; "
        f"filename*=UTF-8''{_quote(row.name)}",
    }
    return Response(
        data,
        media_type=row.mime if inline else "application/octet-stream",
        headers=headers,
    )


@router.delete("/attachments/{attachment_id}")
async def delete(request: Request, attachment_id: str) -> dict[str, bool]:
    await svc(request).delete(attachment_id)
    return {"ok": True}


def _quote(name: str) -> str:
    from urllib.parse import quote  # noqa: PLC0415

    return quote(name, safe="")
