"""AskUserQuestion registry: one Future per pending question (like approvals)."""

import asyncio
from dataclasses import dataclass, field

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id

QUESTION_NOT_FOUND = 2003
QUESTION_TIMEOUT = 2004
ANSWER_INVALID = 2005


@dataclass
class Answer:
    selected: list[str]
    other: str | None = None


@dataclass
class _Pending:
    session_id: str
    labels: list[str]
    multi_select: bool
    future: asyncio.Future[Answer] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )


class QuestionRegistry:
    def __init__(self) -> None:
        self._pending: dict[str, _Pending] = {}

    def create(self, session_id: str, labels: list[str], *, multi_select: bool) -> str:
        qid = new_public_id("Q")
        self._pending[qid] = _Pending(session_id, labels, multi_select)
        return qid

    def pending_ids(self, session_id: str | None = None) -> list[str]:
        return [
            i
            for i, p in self._pending.items()
            if not p.future.done()
            and (session_id is None or p.session_id == session_id)
        ]

    async def wait(self, qid: str, timeout_s: float) -> Answer:
        """The answer, or DomainException(2004) on timeout."""
        pending = self._pending[qid]
        try:
            return await asyncio.wait_for(pending.future, timeout_s)
        except TimeoutError as exc:
            raise DomainException(QUESTION_TIMEOUT) from exc
        finally:
            self._pending.pop(qid, None)

    def discard(self, qid: str) -> None:
        """Forget a question whose waiter is gone (cancel, disconnect, timeout)."""
        pending = self._pending.pop(qid, None)
        if pending is not None and not pending.future.done():
            pending.future.cancel()

    def resolve(self, qid: str, selected: list[str], other: str | None) -> None:
        pending = self._pending.get(qid)
        if pending is None or pending.future.done():
            raise DomainException(QUESTION_NOT_FOUND)
        other = (other or "").strip() or None
        bad = [s for s in selected if s not in pending.labels]
        too_many = len(selected) > 1 and not pending.multi_select
        if bad or too_many or not (selected or other):
            raise DomainException(ANSWER_INVALID)
        pending.future.set_result(Answer(selected, other))
