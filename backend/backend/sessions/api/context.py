from dot_contracts.sessions import (
    CompactIn,
    CompactionRecordOut,
    CompactOut,
    ContextInfo,
)
from fastapi import Request

from backend.core.api.auth import protected_router
from backend.core.exceptions import DomainException
from backend.sessions.services.compaction.tokens import row_tokens
from backend.sessions.services.session_service import SessionService
from backend.sessions.services.transcript_tokens import estimate_tokens

router = protected_router(prefix="/v1/sessions", tags=["sessions"])
COMPACTION_FAILED = 2020


async def _system_text(request: Request, public_id: str) -> str:
    state = request.app.state
    suffix = await state.tiers.suffix(public_id)
    return state.react.system_for(suffix.text)


@router.post("/{session_id}/compact")
async def compact(
    request: Request, session_id: str, body: CompactIn | None = None
) -> CompactOut:
    """Compact now (all stages, regardless of size). 2001 while a turn runs."""
    state = request.app.state
    row = await SessionService(state.sessions).get(session_id)
    state.turns.claim(row.public_id)
    try:
        system = await _system_text(request, row.public_id)
        try:
            out = await state.compactor.compact_now(
                row.id, row.public_id, system, body.focus if body else None
            )
        except DomainException as exc:
            raise DomainException(COMPACTION_FAILED) from exc
    finally:
        state.turns.release(row.public_id)
    return CompactOut(
        compacted=out.compacted,
        reason=out.reason,
        tokens_before=out.tokens_before,
        tokens_after=out.tokens_after,
        stages=out.stages,
    )


@router.get("/{session_id}/context")
async def context(request: Request, session_id: str) -> ContextInfo:
    state = request.app.state
    row = await SessionService(state.sessions).get(session_id)
    suffix = await state.tiers.suffix(row.public_id)
    system = state.react.system_for(suffix.text)
    used, source = await state.compactor.used(row.id, system)
    per_role: dict[str, int] = {}
    for r in await state.store.load(row.id):
        per_role[r.role] = per_role.get(r.role, 0) + row_tokens(r)
    history = await state.store.overlay.history(row.id)
    return ContextInfo(
        limit=state.settings.llm_context_limit,
        threshold=state.compactor.threshold,
        used=used,
        source=source,
        tiers={"prefix": estimate_tokens(state.react.prefix_text), **suffix.parts},
        messages=per_role,
        compactions=[
            CompactionRecordOut(
                id=c.id,
                trigger=c.trigger,
                stages=list(c.stages),
                tokens_before=c.tokens_before,
                tokens_after=c.tokens_after,
                summary_seq=c.summary_seq,
                undone=c.undone,
                created_at=c.created_at,
            )
            for c in history
        ],
    )
