"""In-memory stand-ins so a subagent can reuse ReactEngine and ToolRunner."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from backend.sessions.models import Message
from backend.sessions.services.compaction.tokens import row_tokens
from backend.sessions.services.compactor import Outcome
from backend.sessions.services.transcript_tokens import estimate_tokens

DROPPED = "[Older tool output dropped to fit the context window.]"
TRIM_TO = 0.8  # share of the context limit a child keeps after trimming


class EphemeralStore:
    """Transcript of one subagent run: never persisted, mode follows the parent."""

    def __init__(self, mode: Callable[[], Awaitable[str]]) -> None:
        self._mode = mode
        self._rows: list[Message] = []

    async def append(  # noqa: PLR0913
        self,
        session_pk: int,
        role: str,
        content: str = "",
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        reminder: str | None = None,
        tainted: bool = False,
        reasoning: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Message:
        row = Message(
            session_id=session_pk,
            seq=len(self._rows) + 1,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            reminder=reminder,
            token_count=0,
            rewound=False,
            tainted=tainted,
            reasoning=reasoning or None,
            meta=meta,
            created_at=datetime.now(UTC),
        )
        self._rows.append(row)
        return row

    async def load(self, _session_pk: int, **_kw: Any) -> list[Message]:
        return list(self._rows)

    async def last_seq(self, _session_pk: int) -> int:
        return len(self._rows)

    async def mode_of(self, _session_pk: int) -> str:
        return await self._mode()

    def trim(self, system_tokens: int, budget: int) -> tuple[int, int]:
        """Blank the oldest tool outputs until the rows fit; (before, after)."""
        total = system_tokens + sum(row_tokens(r) for r in self._rows)
        before = total
        for row in self._rows:
            if total <= budget:
                break
            if row.role == "tool" and row.view_content is None:
                saved = row_tokens(row)
                row.view_content = DROPPED
                total -= saved - row_tokens(row)
        return before, total


class _NoMeter:
    @staticmethod
    def observe(*_a: Any) -> None:
        return None


class ChildTrimmer:
    """Stands in for the Compactor in a subagent loop: a child has no summary
    stage, so a context overflow drops old tool output instead of crashing."""

    meter = _NoMeter()

    def __init__(self, store: EphemeralStore, limit: int) -> None:
        self._store = store
        self._limit = limit

    async def maybe_compact(
        self, _pk: int, _sid: str, system_text: str
    ) -> Outcome | None:
        budget = int(self._limit * TRIM_TO)
        before, after = self._store.trim(estimate_tokens(system_text), budget)
        if after >= before:
            return None
        return Outcome(
            compacted=True,
            tokens_before=before,
            tokens_after=after,
            stages=["microcompact"],
        )


class StaticCompiler:
    """Per-type system prompt; same interface the engine uses on PromptCompiler."""

    def __init__(self, prompt: str) -> None:
        self.system_prompt = prompt
        self.prefix = prompt

    @staticmethod
    def reminder(mode: str, cwd: str, now: datetime, _hint: str = "") -> str:
        return (
            "<system-reminder>\n"
            f"Permission mode: {mode}\nWorking directory: {cwd}\n"
            f"Date: {now.date().isoformat()}\n</system-reminder>"
        )
