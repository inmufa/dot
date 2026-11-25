"""Token accounting: llama-reported prompt tokens when known, else an estimate."""

import json

from backend.cognition.services.engine.images import IMAGE_TOKENS, refs_of
from backend.sessions.models import Message
from backend.sessions.services.transcript_tokens import estimate_tokens


def row_tokens(row: Message) -> int:
    """Estimated model-visible size of one row (content, reminder, tool calls)."""
    if row.role == "plan":
        return 0  # UI only, never sent to the model
    n = estimate_tokens(row.model_text) + estimate_tokens(row.reminder or "")
    if row.tool_calls:
        n += estimate_tokens(json.dumps(row.tool_calls))
    n += IMAGE_TOKENS * len(refs_of(row))  # kept or stubbed: a safe overestimate
    return n + 4  # role/format overhead


def rows_tokens(rows: list[Message]) -> int:
    return sum(row_tokens(r) for r in rows)


class ContextMeter:
    """Remembers the last llama-reported prompt size per session."""

    def __init__(self) -> None:
        self._seen: dict[int, tuple[int, int]] = {}

    def observe(self, session_pk: int, prompt_tokens: int | None, seq: int) -> None:
        """`prompt_tokens` covered every row up to `seq` (inclusive)."""
        if prompt_tokens:
            self._seen[session_pk] = (prompt_tokens, seq)

    def reset(self, session_pk: int) -> None:
        self._seen.pop(session_pk, None)

    def estimate(
        self, session_pk: int, system_tokens: int, rows: list[Message]
    ) -> tuple[int, str]:
        """(tokens, source): reported prompt size plus rows added since, or all estimated."""
        seen = self._seen.get(session_pk)
        if seen is None:
            return system_tokens + rows_tokens(rows), "estimated"
        reported, covered = seen
        return reported + rows_tokens([r for r in rows if r.seq > covered]), "reported"
