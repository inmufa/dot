"""Where to cut old turns from recent ones without splitting tool-call pairs."""

from backend.sessions.models import Message
from backend.sessions.services.compaction.tokens import row_tokens


def _closed_prefixes(rows: list[Message]) -> list[bool]:
    """closed[i]: rows[:i] have no assistant tool call still waiting for a result."""
    open_ids: set[str] = set()
    closed = [True]
    for row in rows:
        if row.role == "assistant":
            open_ids.update(str(c.get("id")) for c in row.tool_calls or [])
        elif row.role == "tool":
            open_ids.discard(row.tool_call_id or "")
        closed.append(not open_ids)
    return closed


def choose_cut(rows: list[Message], keep_tokens: int) -> int | None:
    """Index where the kept tail starts, or None when nothing can be summarised.

    The cut sits before a user or assistant row, never between an assistant
    `tool_calls` message and its tool results, and the head must hold at least
    one row that is not already a summary.
    """
    closed = _closed_prefixes(rows)
    first_real = next((i for i, r in enumerate(rows) if r.role != "summary"), None)
    if first_real is None:
        return None
    total, target = 0, len(rows)
    for i in range(len(rows) - 1, -1, -1):
        total += row_tokens(rows[i])
        if total > keep_tokens:
            break
        target = i

    def valid(i: int) -> bool:
        return (
            first_real < i < len(rows)
            and rows[i].role in ("user", "assistant")
            and closed[i]
        )

    for i in range(min(target, len(rows) - 1), first_real, -1):
        if valid(i):
            return i
    for i in range(target + 1, len(rows)):
        if valid(i):
            return i
    return None
