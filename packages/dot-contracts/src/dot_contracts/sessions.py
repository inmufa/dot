"""Public session DTOs served under /v1/sessions."""

from typing import Any

from pydantic import BaseModel, Field

from dot_contracts.permissions import PermissionMode
from dot_contracts.types import UtcDatetime


class SessionInfo(BaseModel):
    id: str
    mode: PermissionMode
    title: str | None = None
    created_at: UtcDatetime


class Message(BaseModel):
    seq: int
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    created_at: UtcDatetime
    rewound: bool = False
    compacted: bool = False  # folded into a summary row (include_compacted=1)
    tainted: bool = False
    meta: dict[str, Any] | None = None  # engine markers, e.g. reasoning_promoted


class RewindIn(BaseModel):
    to_seq: int = Field(ge=0)


class RestoredFile(BaseModel):
    path: str
    action: str  # restored | deleted


class RewindOut(BaseModel):
    kept_through_seq: int
    rewound_messages: int
    restored: list[RestoredFile]


class CompactOut(BaseModel):
    compacted: bool
    reason: str | None = None  # why nothing happened
    tokens_before: int = 0
    tokens_after: int = 0
    stages: list[str] = Field(default_factory=list)


class CompactionRecordOut(BaseModel):
    id: int
    trigger: str  # auto | manual
    stages: list[str]
    tokens_before: int
    tokens_after: int
    summary_seq: int | None = None
    undone: bool = False  # a later rewind went back past this compaction
    created_at: UtcDatetime


class ContextInfo(BaseModel):
    limit: int
    threshold: int  # compaction triggers at this many tokens
    used: int  # llama-reported when available, else estimated
    source: str  # reported | estimated
    tiers: dict[str, int]  # prefix, global, user, workspace, subdirs, memory, ...
    messages: dict[str, int]  # tokens per role, summary included
    compactions: list[CompactionRecordOut]
