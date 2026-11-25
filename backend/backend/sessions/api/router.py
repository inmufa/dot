from dot_contracts.permissions import PermissionMode
from dot_contracts.sessions import Message, SessionInfo, SessionPatch
from dot_contracts.ui.effort import Effort
from fastapi import Request
from pydantic import BaseModel

from backend.core.api.auth import protected_router
from backend.core.exceptions import DomainException
from backend.sessions.api.info import info, infos
from backend.sessions.services.session_admin import SessionAdmin
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1/sessions", tags=["sessions"])
SESSION_DELETE_UNCONFIRMED = 2030


class CreateSession(BaseModel):
    mode: PermissionMode = PermissionMode.DEFAULT
    project: str | None = None
    effort: Effort = Effort.MEDIUM


class SetMode(BaseModel):
    mode: PermissionMode


def service(request: Request) -> SessionService:
    return SessionService(request.app.state.sessions)


@router.post("", status_code=201)
async def create_session(
    request: Request, body: CreateSession | None = None
) -> SessionInfo:
    body = body or CreateSession()
    row = await SessionAdmin(request.app.state.sessions).create(
        body.mode.value, project=body.project or None, effort=body.effort.value
    )
    return await info(request, row)


@router.get("")
async def list_sessions(  # noqa: PLR0913, PLR0917
    request: Request,
    q: str | None = None,
    pinned: bool | None = None,
    archived: bool | None = None,
    project: str | None = None,
    limit: int = 50,
    before: str | None = None,
) -> list[SessionInfo]:
    rows, hits = await SessionAdmin(request.app.state.sessions).find(
        q=q,
        pinned=pinned,
        archived=archived,
        project=project,
        limit=limit,
        before=before,
    )
    return await infos(request, rows, hits)


@router.patch("/{session_id}")
async def patch_session(
    request: Request, session_id: str, body: SessionPatch
) -> SessionInfo:
    row = await SessionAdmin(request.app.state.sessions).patch(session_id, body)
    return await info(request, row)


@router.delete("/{session_id}")
async def delete_session(
    request: Request, session_id: str, confirm: str | None = None
) -> dict[str, bool]:
    state = request.app.state
    row = await service(request).get(session_id)
    if confirm != row.public_id:
        raise DomainException(SESSION_DELETE_UNCONFIRMED)
    state.turns.claim(row.public_id)  # 2001 while a turn runs
    try:
        await SessionAdmin(state.sessions).delete(row)
    finally:
        state.turns.release(row.public_id)
    return {"ok": True}


@router.get("/{session_id}/messages")
async def list_messages(
    request: Request,
    session_id: str,
    include_rewound: bool = False,
    include_compacted: bool = False,
) -> list[Message]:
    rows = await service(request).messages(
        session_id,
        include_rewound=include_rewound,
        include_compacted=include_compacted,
    )
    return [
        Message(
            seq=r.seq,
            role=r.role,
            content=r.content,
            tool_calls=r.tool_calls,
            tool_call_id=r.tool_call_id,
            created_at=r.created_at,
            rewound=r.rewound,
            compacted=r.compacted_into is not None,
            tainted=r.tainted,
            meta=r.meta,
        )
        for r in rows
    ]


@router.post("/{session_id}/mode")
async def set_mode(request: Request, session_id: str, body: SetMode) -> SessionInfo:
    row = await service(request).set_mode(session_id, body.mode.value)
    # A manual switch ends any EnterPlanMode memory: ExitPlanMode must not
    # restore a mode the user has since replaced.
    request.app.state.agent.previous_mode.pop(session_id, None)
    return await info(request, row)
