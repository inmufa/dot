from dot_contracts.tasks import TaskInfo
from fastapi import Request
from pydantic import BaseModel, Field

from backend.core.api.auth import protected_router
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1", tags=["agent-tools"])


class AnswerIn(BaseModel):
    selected: list[str] = Field(default_factory=list, max_length=4)
    other: str | None = Field(default=None, max_length=10_000)


@router.get("/sessions/{session_id}/tasks")
async def list_tasks(request: Request, session_id: str) -> list[TaskInfo]:
    state = request.app.state
    await SessionService(state.sessions).get(session_id)
    return await state.agent.tasks.list_tasks(session_id)


@router.post("/questions/{question_id}/answer")
async def answer_question(
    request: Request, question_id: str, body: AnswerIn
) -> dict[str, bool]:
    request.app.state.agent.questions.resolve(question_id, body.selected, body.other)
    return {"ok": True}
