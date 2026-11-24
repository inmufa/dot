"""Task list DTO served under /v1/sessions/{id}/tasks."""

from typing import Literal

from pydantic import BaseModel, Field

from dot_contracts.types import UtcDatetime

TaskStatus = Literal["pending", "in_progress", "completed"]


class TaskInfo(BaseModel):
    id: str
    subject: str
    description: str = ""
    status: TaskStatus = "pending"
    blocked_by: list[str] = Field(default_factory=list)
    created_at: UtcDatetime
    updated_at: UtcDatetime
