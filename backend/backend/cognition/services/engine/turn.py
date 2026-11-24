"""Per-turn state and the one-turn-per-session registry."""

import asyncio
from dataclasses import dataclass, field

from backend.core.exceptions import DomainException

SESSION_BUSY = 2001


@dataclass
class Turn:
    pk: int
    public_id: str
    lang: str = "en"
    # Calls announced but not yet answered, in call order.
    open_calls: dict[str, None] = field(default_factory=dict)
    malformed_streak: int = 0
    stop_hooked: bool = False
    empty_retried: bool = False  # the "no visible answer" nudge was already sent
    # Subagent runs: nesting depth, UI label and the root session's public id.
    depth: int = 0
    label: str | None = None
    parent_id: str | None = None


class TurnRegistry:
    def __init__(self) -> None:
        self._active: dict[str, asyncio.Task[None] | None] = {}

    def claim(self, session_id: str) -> None:
        if session_id in self._active:
            raise DomainException(SESSION_BUSY)
        self._active[session_id] = None

    def attach(self, session_id: str, task: asyncio.Task[None]) -> None:
        self._active[session_id] = task

    def release(self, session_id: str, task: asyncio.Task[None] | None = None) -> None:
        """Free the session; with `task`, only if that task still owns the claim."""
        if task is not None and self._active.get(session_id) is not task:
            return
        self._active.pop(session_id, None)

    def is_active(self, session_id: str) -> bool:
        return session_id in self._active

    def stop(self, session_id: str) -> bool:
        task = self._active.get(session_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def cancel_all(self) -> None:
        """Shutdown: cancel every running turn and wait for the tasks to unwind."""
        tasks = [t for t in self._active.values() if t is not None and not t.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
