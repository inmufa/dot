"""Vault tables. Secret columns hold only AES-GCM blobs."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class VaultCredential(Base):
    __tablename__ = "vault_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(80), unique=True)
    origins: Mapped[list[str]] = mapped_column(JSON, default=list)
    username: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    # JSON {"password", "totp_secret"} sealed; None for a session-only entry.
    secret_blob: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    has_totp: Mapped[bool] = mapped_column(Boolean, default=False)
    # Sealed Playwright storage state, scoped to `origins`.
    session_blob: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    session_saved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    session_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    last_used: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )


def meta(row: VaultCredential) -> dict[str, Any]:
    """The only shape that leaves the service: never a secret or session value."""
    return {
        "id": row.public_id,
        "label": row.label,
        "origins": list(row.origins),
        "username": row.username,
        "notes": row.notes,
        "has_password": row.secret_blob is not None,
        "has_totp": row.has_totp,
        "has_session": row.session_blob is not None,
        "session_saved_at": row.session_saved_at,
        "session_expires_at": row.session_expires_at,
        "last_used": row.last_used,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
