from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="default")
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    """Append-only transcript row. Never updated or deleted."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, default=None)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), default=None)
    # Per-turn <system-reminder> frozen at write time so history stays byte-stable.
    reminder: Mapped[str | None] = mapped_column(Text, default=None)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # Set by /rewind: hidden from model context and /messages, never deleted.
    rewound: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Compaction overlay: rows are never deleted, only folded into a summary row.
    compacted_into: Mapped[int | None] = mapped_column(Integer, default=None)
    # Model-visible replacement for `content` (think dropped, Read stubbed).
    view_content: Mapped[str | None] = mapped_column(Text, default=None)
    tainted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Assistant thinking, replayed as reasoning_content so the chat template sees
    # a real <think> block (an empty one makes the model skip </think> later).
    reasoning: Mapped[str | None] = mapped_column(Text, default=None)
    # Engine markers, e.g. {"reasoning_promoted": true}.
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def model_text(self) -> str:
        return self.content if self.view_content is None else self.view_content


class CompactionRecord(Base):
    """One compaction run (auto or manual); feeds GET /context history."""

    __tablename__ = "compactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    trigger: Mapped[str] = mapped_column(String(8))
    stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    tokens_before: Mapped[int] = mapped_column(Integer)
    tokens_after: Mapped[int] = mapped_column(Integer)
    at_seq: Mapped[int] = mapped_column(Integer)  # last seq when it ran
    summary_seq: Mapped[int | None] = mapped_column(Integer, default=None)
    undone: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
