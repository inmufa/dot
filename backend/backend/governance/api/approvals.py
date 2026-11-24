from typing import Literal

from fastapi import Request
from pydantic import BaseModel

from backend.core.api.auth import protected_router

router = protected_router(prefix="/v1/approvals", tags=["approvals"])


class Resolve(BaseModel):
    decision: Literal["allow", "always", "reject"]


@router.post("/{approval_id}/resolve")
async def resolve(request: Request, approval_id: str, body: Resolve) -> dict[str, bool]:
    request.app.state.approvals.resolve(approval_id, body.decision)
    return {"ok": True}
