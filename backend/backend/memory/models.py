from datetime import UTC, datetime

from sqlalchemy import DDL, DateTime, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryFactRow(Base):
    """Index of the fact files in <memory_dir>. The files are the source of truth."""

    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(16), default="project")
    body: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# Full-text index; rowid = memory_facts.id. Plain FTS5, no extension needed.
event.listen(
    MemoryFactRow.__table__,
    "after_create",
    DDL(
        "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts "
        "USING fts5(name, description, body, tokenize='unicode61')"
    ),
)
