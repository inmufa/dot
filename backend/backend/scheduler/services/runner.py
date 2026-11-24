"""Headless turn in a fresh session through the normal engine."""

import asyncio
import logging
from dataclasses import dataclass

from dot_contracts.events import DoneEvent, ErrorEvent, TokenEvent

from backend.cognition.services.engine.react_engine import ReactEngine
from backend.cognition.services.engine.turn import Turn, TurnRegistry
from backend.sessions.services.session_service import SessionService

logger = logging.getLogger(__name__)
SAFE_MODES = ("plan", "default", "acceptEdits", "auto")
TITLE_PREFIX = "[scheduled] "


def safe_mode(mode: str) -> str:
    """A scheduled run never bypasses permissions, whatever the setting says."""
    if mode in SAFE_MODES:
        return mode
    logger.warning(
        "schedule_mode %r is not allowed for scheduled runs; using default", mode
    )
    return "default"


@dataclass
class Outcome:
    status: str  # ok | failed
    detail: str = ""
    session_id: str | None = None


class HeadlessRunner:
    def __init__(
        self,
        engine: ReactEngine,
        sessions: SessionService,
        turns: TurnRegistry,
        *,
        mode: str,
        timeout_s: float,
    ) -> None:
        self._engine = engine
        self._sessions = sessions
        self._turns = turns
        self._mode = safe_mode(mode)
        self._timeout = timeout_s

    async def run(self, prompt: str) -> Outcome:
        row = await self._sessions.create(self._mode)
        await self._sessions.title_from(row.id, TITLE_PREFIX + prompt)
        self._turns.claim(row.public_id)
        turn = Turn(pk=row.id, public_id=row.public_id)
        try:
            try:
                async with asyncio.timeout(self._timeout):
                    return await self._drive(turn, prompt)
            except TimeoutError:
                await self._engine.abort(turn)
                return Outcome("failed", "timed out", row.public_id)
        finally:
            self._turns.release(row.public_id)

    async def _drive(self, turn: Turn, prompt: str) -> Outcome:
        text, error, reason = "", "", "error"
        async for event in self._engine.run(turn, prompt):
            if isinstance(event, TokenEvent) and not event.thinking:
                text = (text + event.text)[-400:]
            elif isinstance(event, ErrorEvent):
                error = f"error {event.code}: {event.message}"
            elif isinstance(event, DoneEvent):
                reason = event.stop_reason
        if reason == "end_turn":
            return Outcome("ok", " ".join(text.split())[-300:], turn.public_id)
        return Outcome("failed", error or reason, turn.public_id)
