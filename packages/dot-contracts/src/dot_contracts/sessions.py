"""Public session DTOs served under /v1/sessions."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from dot_contracts.permissions import PermissionMode
from dot_contracts.types import UtcDatetime
from dot_contracts.ui.effort import Effort

SessionState = Literal["idle", "running", "waiting_approval", "waiting_input"]


class SessionInfo(BaseModel):
    id: str
    mode: PermissionMode
    title: str | None = None
    created_at: UtcDatetime
    pinned: bool = False
    archived: bool = False
    project: str | None = None
    parent_id: str | None = None  # branch source session
    parent_seq: int | None = None  # rows with seq <= this were copied
    effort: Effort = Effort.MEDIUM
    last_message_at: UtcDatetime | None = None
    message_count: int = 0  # visible rows (not rewound, not compacted)
    state: SessionState = "idle"
    snippet: str | None = None  # search hit excerpt (list with q only)


class SessionPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    pinned: bool | None = None
    archived: bool | None = None
    project: str | None = None  # "" clears
    effort: Effort | None = None


class BranchIn(BaseModel):
    from_seq: int = Field(ge=1)  # copy rows with seq < from_seq


class BranchOut(BaseModel):
    session: SessionInfo
    parent_seq: int  # actual cut (moved back to a turn boundary)


class CompactIn(BaseModel):
    focus: str | None = Field(default=None, max_length=1000)


class RegenerateIn(BaseModel):
    restore_files: bool = False
    effort: Effort | None = None


class BtwIn(BaseModel):
    question: str = Field(min_length=1, max_length=20_000)


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
