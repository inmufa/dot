from datetime import UTC, datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class McpTrust(Base):
    """One-time approval of a project-scoped server. A changed config needs a new one."""

    __tablename__ = "mcp_trust"
    __table_args__ = (UniqueConstraint("name", "fingerprint", name="uq_mcp_trust"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    fingerprint: Mapped[str] = mapped_column(String(64))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
