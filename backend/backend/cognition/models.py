from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Task(Base):
    """One node of the session task DAG (`blocked_by` holds public ids)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(10), index=True)  # root session
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    blocked_by: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
