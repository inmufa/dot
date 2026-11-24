from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True)
    kind: Mapped[str] = mapped_column(String(8), default="user")  # user | builtin
    cron: Mapped[str] = mapped_column(String(100))
    # user: the prompt of a fresh session per run. builtin: the task key.
    prompt: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_status: Mapped[str | None] = mapped_column(String(16), default=None)


class JobRun(Base):
    __tablename__ = "scheduled_job_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    status: Mapped[str] = mapped_column(String(16), default="running")
    session_id: Mapped[str | None] = mapped_column(String(10), default=None)
    detail: Mapped[str] = mapped_column(Text, default="")
    seq: Mapped[int] = mapped_column(Integer, default=0)
