from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.cognition.services.engine.chat_stream import stream_turn
from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.skills.render import expand_slash
from backend.core.api.auth import protected_router
from backend.core.api.language import resolve_language
from backend.core.api.ratelimit import MESSAGE_TOO_LONG, enforce_chat_rate
from backend.core.exceptions import DomainException
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1/sessions", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)  # upper bound: DOT_MAX_MESSAGE_CHARS


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
    )
    return StreamingResponse(
        stream_turn(state.react, state.turns, turn, text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/stop")
async def stop(request: Request, session_id: str) -> dict[str, bool]:
    row = await SessionService(request.app.state.sessions).get(session_id)
    return {"ok": True, "stopped": request.app.state.turns.stop(row.public_id)}
