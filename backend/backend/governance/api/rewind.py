from dot_contracts.sessions import RewindIn, RewindOut
from fastapi import Request

from backend.core.api.auth import protected_router

router = protected_router(prefix="/v1/sessions", tags=["sessions"])


@router.post("/{session_id}/rewind")
async def rewind(request: Request, session_id: str, body: RewindIn) -> RewindOut:
    return await request.app.state.checkpoints.rewind(session_id, body.to_seq)
