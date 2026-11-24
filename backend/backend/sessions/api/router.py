from dot_contracts.permissions import PermissionMode
from dot_contracts.sessions import Message, SessionInfo
from fastapi import Request
from pydantic import BaseModel

from backend.core.api.auth import protected_router
from backend.sessions.models import Session
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1/sessions", tags=["sessions"])


class CreateSession(BaseModel):
    mode: PermissionMode = PermissionMode.DEFAULT


class SetMode(BaseModel):
    mode: PermissionMode


def service(request: Request) -> SessionService:
    return SessionService(request.app.state.sessions)


def to_info(row: Session) -> SessionInfo:
    return SessionInfo(
        id=row.public_id,
        mode=PermissionMode(row.mode),
        title=row.title,
        created_at=row.created_at,
    )


@router.post("", status_code=201)
async def create_session(
    request: Request, body: CreateSession | None = None
) -> SessionInfo:
    mode = body.mode if body else PermissionMode.DEFAULT
    return to_info(await service(request).create(mode.value))


@router.get("")
async def list_sessions(request: Request) -> list[SessionInfo]:
    return [to_info(r) for r in await service(request).recent()]


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
    return to_info(row)
