from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from dot_contracts.permissions import PermissionMode
from dot_contracts.types import UtcDatetime


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    role: Role
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str | None = None


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskNode(BaseModel):
    public_id: str
    subject: str
    status: TaskStatus = TaskStatus.PENDING
    blocked_by: list[str] = Field(default_factory=list)


class SessionInfo(BaseModel):
    public_id: str
    mode: PermissionMode = PermissionMode.DEFAULT
    created_at: UtcDatetime
    title: str | None = None


class CompactionSummary(BaseModel):
    summary: str
    restored_files: list[str] = Field(default_factory=list)
    tokens_before: int
    tokens_after: int


class MemoryKind(StrEnum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


class MemoryFact(BaseModel):
    id: str
    name: str
    description: str
    kind: MemoryKind = MemoryKind.PROJECT
    body: str
    updated_at: UtcDatetime


class MemoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=200)
    kind: MemoryKind = MemoryKind.PROJECT
    body: str = Field(min_length=1, max_length=8000)


class MemoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)
    kind: MemoryKind | None = None
    body: str | None = Field(default=None, min_length=1, max_length=8000)
