"""Attachment rows (uploads stored in the workspace under uploads/<session>/)."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class AttachmentRow(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(10), index=True)  # public id
    name: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(12))
    path: Mapped[str] = mapped_column(String(500))
    text_path: Mapped[str | None] = mapped_column(String(520), default=None)
    pages: Mapped[int | None] = mapped_column(Integer, default=None)
    extracted_chars: Mapped[int | None] = mapped_column(Integer, default=None)
    extracted: Mapped[str | None] = mapped_column(Text, default=None)  # capped text
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
