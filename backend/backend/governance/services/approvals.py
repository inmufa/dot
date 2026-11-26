"""In-memory approval registry: one Future per pending approval."""

import asyncio
from dataclasses import dataclass, field

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.core.session_ids import root_of

APPROVAL_TIMEOUT = 3001
APPROVAL_NOT_FOUND = 3003


@dataclass
class _Pending:
    session_id: str
    future: asyncio.Future[str] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )


class ApprovalRegistry:
    def __init__(self) -> None:
        self._pending: dict[str, _Pending] = {}
        self._always: dict[str, set[str]] = {}

    def create(self, session_id: str) -> str:
        approval_id = new_public_id("A")
        self._pending[approval_id] = _Pending(session_id)
        return approval_id

    def pending_ids(self, session_id: str | None = None) -> list[str]:
        return [
            i
            for i, p in self._pending.items()
            if not p.future.done()
            and (session_id is None or p.session_id == session_id)
        ]

    async def wait(self, approval_id: str, timeout_s: float) -> str:
        """Return the decision or raise DomainException(3001) on timeout."""
        pending = self._pending[approval_id]
        try:
            return await asyncio.wait_for(pending.future, timeout_s)
        except TimeoutError as exc:
            raise DomainException(APPROVAL_TIMEOUT) from exc
        finally:
            self._pending.pop(approval_id, None)

    def discard(self, approval_id: str) -> None:
        """Forget an approval whose waiter is gone (cancel, disconnect, timeout)."""
        pending = self._pending.pop(approval_id, None)
        if pending is not None and not pending.future.done():
            pending.future.cancel()

    def resolve(self, approval_id: str, decision: str) -> None:
        pending = self._pending.get(approval_id)
        if pending is None or pending.future.done():
            raise DomainException(APPROVAL_NOT_FOUND)
        pending.future.set_result(decision)

    def allowed(self, session_id: str) -> set[str]:
        return self._always.setdefault(root_of(session_id), set())  # subagents share
