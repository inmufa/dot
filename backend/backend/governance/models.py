from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    """Append-only decision log. Triggers below reject UPDATE and DELETE."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True)
    session_id: Mapped[str] = mapped_column(String(10), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    tool: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


for _op in ("UPDATE", "DELETE"):
    event.listen(
        AuditLog.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER IF NOT EXISTS audit_log_no_{_op.lower()} "
            f"BEFORE {_op} ON audit_log "
            "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END"
        ),
    )


class Checkpoint(Base):
    """Pre-write snapshot kept in the sandbox; this row says where and when."""

    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    call_id: Mapped[str] = mapped_column(String(64))
    sandbox_id: Mapped[str] = mapped_column(String(16))
    path: Mapped[str] = mapped_column(Text)
    # seq of the tool message that will carry this call's result
    msg_seq: Mapped[int] = mapped_column(Integer)
    restored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
