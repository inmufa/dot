"""Public audit-log DTOs served under /v1/audit."""

from typing import Any

from pydantic import BaseModel

from dot_contracts.permissions import Decision
from dot_contracts.types import UtcDatetime


class AuditEntry(BaseModel):
    id: str
    session: str
    mode: str
    tool: str
    args: dict[str, Any]
    decision: Decision
    source: str  # rule | mode | hook | classifier | user
    reason: str
    created_at: UtcDatetime


class AuditPage(BaseModel):
    items: list[AuditEntry]
    next_cursor: str | None = None
