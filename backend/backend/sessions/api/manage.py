"""Session operations: export, regenerate, branch, clear, btw, usage, commands."""

import json
import re
from collections.abc import AsyncIterator
from typing import Literal

from dot_contracts.events import DoneEvent, ErrorEvent, TokenEvent
from dot_contracts.sessions import (
    BranchIn,
    BranchOut,
    BtwIn,
    RegenerateIn,
    SessionInfo,
)
from dot_contracts.ui.commands import CommandInfo
from dot_contracts.ui.telemetry import UsageOut
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from backend.cognition.services.engine.chat_stream import sse, stream_turn
from backend.cognition.services.engine.history import to_chat_messages
from backend.cognition.services.engine.turn import Turn, TurnOptions
from backend.core.api.auth import protected_router
from backend.core.api.envelope import build_envelope
from backend.core.api.language import resolve_language
from backend.core.api.ratelimit import enforce_chat_rate
from backend.core.exceptions import DomainException
from backend.routing.clients.llm_types import StreamOptions, TextDelta
from backend.sessions.api.info import info
from backend.sessions.services.branching import branch as branching
from backend.sessions.services.commands import export, registry, usage
from backend.sessions.services.session_admin import SessionAdmin
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1", tags=["session-ops"])
BTW_MAX_TOKENS = 600
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


async def _rows(request: Request, public_id: str):
    state = request.app.state
    row = await SessionService(state.sessions).get(public_id)
    return row, await state.store.load(row.id, include_compacted=True)


@router.get("/sessions/{session_id}/export")
async def export_session(
    request: Request,
    session_id: str,
    format: Literal["md", "json"] = "md",  # noqa: A002
    include_thinking: bool = False,
) -> Response:
    row, rows = await _rows(request, session_id)
    rows = [r for r in rows if r.role != "summary"]
    name = _SAFE.sub("_", f"dot-{row.public_id}")
    if format == "json":
        body = json.dumps(
            export.to_json(row, rows, include_thinking=include_thinking), indent=2
        )
        media, ext = "application/json", "json"
    else:
        body = export.to_markdown(row, rows, include_thinking=include_thinking)
        media, ext = "text/markdown; charset=utf-8", "md"
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'},
    )


@router.post("/sessions/{session_id}/regenerate")
async def regenerate(
    request: Request, session_id: str, body: RegenerateIn | None = None
) -> StreamingResponse:
    body = body or RegenerateIn()
    state = request.app.state
    enforce_chat_rate(request)
    row = await SessionService(state.sessions).get(session_id)
    user = await branching.last_user_turn(state.sessions, row.id)
    prev = max(
        (
            r.seq
            for r in await state.store.load(row.id, include_compacted=True)
            if r.seq < user.seq and r.role != "summary"
        ),
        default=0,
    )
    if body.restore_files:  # claims the session itself while it rewinds
        await state.checkpoints.rewind(row.public_id, prev)
    state.turns.claim(row.public_id)
    try:
        if not body.restore_files:
            await branching.rewind_from(state.sessions, row.id, user.seq)
            await state.store.uncompact_after_rewind(row.id, user.seq - 1)
            state.gov.taint.reset(row.public_id)
    except BaseException:
        state.turns.release(row.public_id)
        raise
    turn = Turn(
        pk=row.id,
        public_id=row.public_id,
        lang=resolve_language(request.headers.get("accept-language")),
        options=TurnOptions(effort=body.effort),
    )
    return StreamingResponse(
        stream_turn(state.react, state.turns, turn, user.content),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/branch")
async def branch(request: Request, session_id: str, body: BranchIn) -> BranchOut:
    state = request.app.state
    src = await SessionService(state.sessions).get(session_id)
    new = await branching.branch(state.sessions, src, body.from_seq)
    return BranchOut(session=await info(request, new), parent_seq=new.parent_seq or 0)


@router.post("/sessions/{session_id}/clear", status_code=201)
async def clear(request: Request, session_id: str) -> SessionInfo:
    state = request.app.state
    src = await SessionService(state.sessions).get(session_id)
    new = await SessionAdmin(state.sessions).create(
        src.mode, project=src.project, effort=src.effort
    )
    return await info(request, new)


async def _btw_stream(
    request: Request, session_id: str, question: str
) -> AsyncIterator[str]:
    state = request.app.state
    lang = resolve_language(request.headers.get("accept-language"))
    try:
        row, rows = await _rows(request, session_id)
        visible = [r for r in rows if r.compacted_into is None]
        suffix = await state.tiers.suffix(row.public_id)
        system = state.react.system_for(suffix.text)
        history = branching.cut_rows(visible, 10**9)
        summaries = [r for r in visible if r.role == "summary"]
        messages = to_chat_messages(system, sorted(summaries + history, key=_order))
        note = "<system-reminder>\nThis is a side question: answer briefly from the conversation; no tools are available.\n</system-reminder>"
        messages.append({"role": "user", "content": f"{question}\n\n{note}"})
        options = StreamOptions(thinking=False, max_tokens=BTW_MAX_TOKENS)
        async for item in state.llm.stream(messages, [], options):
            if isinstance(item, TextDelta) and not item.thinking:
                yield sse(TokenEvent(text=item.text))
        yield sse(DoneEvent(stop_reason="end_turn"))
    except DomainException as exc:
        _, err = build_envelope(exc.code, lang)
        yield sse(ErrorEvent(code=exc.code, message=err["messages"][0]))
        yield sse(DoneEvent(stop_reason="error"))


def _order(row) -> tuple[bool, int]:
    return (row.role != "summary", row.seq)


@router.post("/sessions/{session_id}/btw")
async def btw(request: Request, session_id: str, body: BtwIn) -> StreamingResponse:
    await SessionService(request.app.state.sessions).get(session_id)
    return StreamingResponse(
        _btw_stream(request, session_id, body.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/usage")
async def session_usage(request: Request, session_id: str) -> UsageOut:
    state = request.app.state
    row, rows = await _rows(request, session_id)
    suffix = await state.tiers.suffix(row.public_id)
    system = state.react.system_for(suffix.text)
    used, _ = await state.compactor.used(row.id, system)
    return usage.aggregate(rows, used, state.settings.llm_context_limit)


@router.get("/commands")
async def commands(request: Request, session: str | None = None) -> list[CommandInfo]:
    state = request.app.state
    rows = None
    if session:
        _, rows = await _rows(request, session)
        rows = [r for r in rows if not r.rewound]
    out = registry.client_commands() + registry.server_commands()
    if rows is not None:
        for cmd in out:
            if cmd.kind == "server" and (why := registry.availability(cmd.name, rows)):
                cmd.available, cmd.reason = False, why
    taken = {c.name for c in out}
    for skill in sorted(state.skills.index().skills.values(), key=lambda s: s.name):
        if skill.name in taken:
            continue
        out.append(
            CommandInfo(
                name=skill.name,
                description=skill.description,
                group="skills",
                args=[],
                kind="skill",
                available=skill.available,
                reason=skill.reason,
            )
        )
    return out
