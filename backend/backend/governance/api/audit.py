from typing import Annotated

from dot_contracts.audit import AuditEntry, AuditPage
from dot_contracts.permissions import Decision
from fastapi import Query, Request

from backend.core.api.auth import protected_router

router = protected_router(prefix="/v1/audit", tags=["audit"])


@router.get("")
async def list_audit(
    request: Request,
    session: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: int | None = None,
) -> AuditPage:
    rows, nxt = await request.app.state.audit.page(session, limit, cursor)
    items = [
        AuditEntry(
            id=r.public_id,
            session=r.session_id,
            mode=r.mode,
            tool=r.tool,
            args=r.args,
            decision=Decision(r.decision),
            source=r.source,
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return AuditPage(items=items, next_cursor=str(nxt) if nxt else None)
