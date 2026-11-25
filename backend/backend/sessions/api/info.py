"""SessionInfo assembly: columns, activity stats and the live run state."""

from typing import Any

from dot_contracts.permissions import PermissionMode
from dot_contracts.sessions import SessionInfo, SessionState
from dot_contracts.ui.effort import Effort
from fastapi import Request

from backend.sessions.models import Session
from backend.sessions.services.session_admin import SessionAdmin


def run_state(state: Any, public_id: str) -> SessionState:
    if state.approvals.pending_ids(public_id):
        return "waiting_approval"
    if state.agent.questions.pending_ids(public_id):
        return "waiting_input"
    return "running" if state.turns.is_active(public_id) else "idle"


async def infos(
    request: Request, rows: list[Session], hits: dict[int, str] | None = None
) -> list[SessionInfo]:
    state = request.app.state
    act = await SessionAdmin(state.sessions).activity([r.id for r in rows])
    out = []
    for r in rows:
        a = act.get(r.id)
        out.append(
            SessionInfo(
                id=r.public_id,
                mode=PermissionMode(r.mode),
                title=r.title,
                created_at=r.created_at,
                pinned=bool(r.pinned),
                archived=bool(r.archived),
                project=r.project,
                parent_id=r.parent_id,
                parent_seq=r.parent_seq,
                effort=Effort(r.effort or "medium"),
                last_message_at=a.last_message_at if a else None,
                message_count=a.count if a else 0,
                state=run_state(state, r.public_id),
                snippet=(hits or {}).get(r.id),
            )
        )
    return out


async def info(request: Request, row: Session) -> SessionInfo:
    return (await infos(request, [row]))[0]
