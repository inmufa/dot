from dot_contracts.ui.effort import Effort
from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.cognition.services.engine.chat_stream import stream_turn
from backend.cognition.services.engine.turn import Turn, TurnOptions
from backend.cognition.services.skills.render import expand_slash
from backend.core.api.auth import protected_router
from backend.core.api.language import resolve_language
from backend.core.api.ratelimit import MESSAGE_TOO_LONG, enforce_chat_rate
from backend.core.exceptions import DomainException
from backend.sessions.services.auto_title import retitle
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1/sessions", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)  # upper bound: DOT_MAX_MESSAGE_CHARS
    effort: Effort | None = None  # this turn only; default is the session's effort
    plan: bool = False  # plan first: read-only turn ending in ExitPlanMode
    research: bool = False  # research protocol with citations
    research_seconds: int | None = Field(default=None, ge=30, le=1800)
    attachments: list[str] = Field(default_factory=list, max_length=5)  # ids
    voice: bool = False  # voice reply: thinking off, short answer


@router.post("/{session_id}/chat")
async def chat(
    request: Request, session_id: str, body: ChatRequest
) -> StreamingResponse:
    state = request.app.state
    if len(body.message) > state.settings.max_message_chars:
        raise DomainException(MESSAGE_TOO_LONG)
    enforce_chat_rate(request)
    sessions = SessionService(state.sessions)
    row = await sessions.get(session_id)
    if body.attachments:  # 4103 before the turn is claimed
        await state.attachments.resolve(row.public_id, body.attachments)
    state.turns.claim(row.public_id)  # 2001 if busy; released when the turn task ends
    try:
        await sessions.title_from(row.id, body.message)
    except BaseException:
        state.turns.release(row.public_id)
        raise
    await state.skills.ensure_binaries()
    text = expand_slash(body.message, state.skills.get) or body.message
    turn = Turn(
        pk=row.id,
        public_id=row.public_id,
        lang=resolve_language(request.headers.get("accept-language")),
        options=TurnOptions(
            effort=body.effort,
            plan=body.plan,
            research=body.research,
            research_seconds=body.research_seconds,
            attachments=body.attachments,
            voice=body.voice,
        ),
    )
    return StreamingResponse(
        stream_turn(
            state.react,
            state.turns,
            turn,
            text,
            after=(lambda: retitle(sessions, state.llm, row.public_id))
            if state.settings.auto_title
            else None,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/stop")
async def stop(request: Request, session_id: str) -> dict[str, bool]:
    row = await SessionService(request.app.state.sessions).get(session_id)
    return {"ok": True, "stopped": request.app.state.turns.stop(row.public_id)}


class InjectRequest(BaseModel):
    message: str = Field(min_length=1)


@router.post("/{session_id}/inject")
async def inject(
    request: Request, session_id: str, body: InjectRequest
) -> dict[str, bool]:
    """Hand a message to the running turn; it joins before the next model call."""
    state = request.app.state
    if len(body.message) > state.settings.max_message_chars:
        raise DomainException(MESSAGE_TOO_LONG)
    row = await SessionService(state.sessions).get(session_id)
    if not state.turns.is_active(row.public_id):
        return {"queued": False}  # turn already over: the caller sends it normally
    state.react.inbox.setdefault(row.public_id, []).append(body.message)
    return {"queued": True}


@router.post("/{session_id}/inject/cancel")
async def inject_cancel(
    request: Request, session_id: str, body: InjectRequest
) -> dict[str, bool]:
    """Take a handed-over message back (the user retracted it before it joined)."""
    state = request.app.state
    row = await SessionService(state.sessions).get(session_id)
    box = state.react.inbox.get(row.public_id, [])
    if body.message not in box:
        return {"removed": False}
    box.remove(body.message)
    return {"removed": True}
