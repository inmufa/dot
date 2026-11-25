"""Engine hooks: resolve the turn's effort, add its hint, supply StreamOptions."""

import logging
import time
from typing import Any

from dot_contracts.events import UsageEvent
from dot_contracts.ui.effort import Effort

from backend.cognition.services.engine.effort.profiles import (
    EffortState,
    build_state,
    effective,
)
from backend.cognition.services.engine.turn import Turn
from backend.core.exceptions import DomainException
from backend.routing.clients.llm_types import LLMClient, LLMFinish, StreamOptions
from backend.sessions.services.session_service import SessionService

logger = logging.getLogger(__name__)
LEVELS_TTL_S = 30.0  # a model switch changes the template caps
SELF_CHECK = (
    "<system-reminder>\nSelf-check: re-read the user's request and your last answer. "
    "If you find an error or something missing, fix it and give the corrected final "
    "answer. If it is fully correct, reply only with: Verified.\n</system-reminder>"
)


class EffortProvider:
    def __init__(self, llm: LLMClient, sessions: SessionService) -> None:
        self._llm = llm
        self._sessions = sessions
        self._levels: list[str] | None = None
        self._probed = 0.0

    async def _native_levels(self) -> list[str]:
        if self._levels is None or time.monotonic() - self._probed > LEVELS_TTL_S:
            probe = getattr(self._llm, "reasoning_levels", None)
            try:
                self._levels = list(await probe()) if probe else []
            except Exception:  # probe must never break a turn
                logger.warning("reasoning level probe failed", exc_info=True)
                self._levels = []
            self._probed = time.monotonic()
        return self._levels

    async def reminder(self, turn: Turn) -> str:
        """Resolve the effort (first hook to run) and return the hint block."""
        requested = turn.options.effort
        if requested is None:
            try:
                requested = Effort((await self._sessions.get(turn.public_id)).effort)
            except (DomainException, ValueError):
                requested = Effort.MEDIUM
        level, ultra = effective(requested, turn.text, voice=turn.options.voice)
        state = build_state(
            requested,
            level,
            ultrathink=ultra,
            native_levels=await self._native_levels(),
        )
        turn.effort_state = state
        hint = state.profile.hint
        if turn.options.voice:
            hint = "Voice reply: answer in one or two short spoken sentences."
        return f"<system-reminder>\n{hint}\n</system-reminder>" if hint else ""

    @staticmethod
    def options(turn: Turn) -> StreamOptions | None:
        state: EffortState | None = turn.effort_state
        return state.options if state else None


def usage_meta(turn: Turn, finish: LLMFinish, duration_ms: int) -> dict[str, Any]:
    state: EffortState | None = turn.effort_state
    return {
        "prompt_tokens": finish.prompt_tokens,
        "completion_tokens": finish.completion_tokens,
        "duration_ms": duration_ms,
        "effort": state.info.level.value if state else None,
        "thinking": state.info.thinking if state else None,
    }


def enrich_usage(
    event: UsageEvent, turn: Turn, finish: LLMFinish, duration_ms: int
) -> UsageEvent:
    event.prompt_tokens = finish.prompt_tokens
    event.completion_tokens = finish.completion_tokens
    event.duration_ms = duration_ms
    if finish.completion_tokens and duration_ms > 0:
        event.tokens_per_s = round(finish.completion_tokens * 1000 / duration_ms, 1)
    state: EffortState | None = turn.effort_state
    event.effort = state.info if state else None
    return event
