"""Append-only audit log. There is deliberately no update or delete method."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.logging import redact, scrub
from backend.core.public_id import new_public_id
from backend.governance.models import AuditLog

MAX_VALUE_CHARS = 500


def clean_args(value: Any) -> Any:
    """redact() plus bearer scrubbing and clipping of long strings."""
    value = redact(value)
    return _clip(value)


def _clip(value: Any) -> Any:
    if isinstance(value, str):
        text = scrub(value)
        return text if len(text) <= MAX_VALUE_CHARS else text[:MAX_VALUE_CHARS] + "..."
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clip(v) for v in value]
    return value


class AuditService:
    def __init__(self, maker: async_sessionmaker) -> None:
        self._maker = maker

    async def append(  # noqa: PLR0913
        self,
        *,
        session: str,
        mode: str,
        tool: str,
        args: dict[str, Any],
        decision: str,
        source: str,
        reason: str = "",
    ) -> None:
        async with self._maker() as db:
            db.add(
                AuditLog(
                    public_id=new_public_id("A"),
                    session_id=session,
                    mode=mode,
                    tool=tool,
                    args=clean_args(args),
                    decision=decision,
                    source=source,
                    reason=reason[:500],
                )
            )
            await db.commit()

    async def page(
        self, session: str | None, limit: int, before: int | None
    ) -> tuple[list[AuditLog], int | None]:
        """Newest first. Returns (rows, next cursor or None)."""
        async with self._maker() as db:
            q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit + 1)
            if session:
                q = q.where(AuditLog.session_id == session)
            if before is not None:
                q = q.where(AuditLog.id < before)
            rows = list((await db.scalars(q)).all())
        more = len(rows) > limit
        rows = rows[:limit]
        return rows, (rows[-1].id if more and rows else None)
