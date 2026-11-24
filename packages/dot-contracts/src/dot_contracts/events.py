from typing import Annotated, Literal

from pydantic import BaseModel, Field

from dot_contracts.permissions import ClassifierVerdict
from dot_contracts.tools import ToolInvocation, ToolResult


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str
    thinking: bool = False


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    invocation: ToolInvocation


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    result: ToolResult


class ApprovalRequiredEvent(BaseModel):
    type: Literal["approval_required"] = "approval_required"
    approval_id: str
    invocation: ToolInvocation
    diff: str | None = None
    verdict: ClassifierVerdict | None = None
    # Set when a subagent (not the main agent) is asking: its label, e.g. "Explore 1".
    subagent: str | None = None


class QuestionOption(BaseModel):
    label: str
    description: str = ""


class QuestionEvent(BaseModel):
    """AskUserQuestion: answer with POST /v1/questions/{question_id}/answer."""

    type: Literal["question"] = "question"
    question_id: str
    question: str
    options: list[QuestionOption]
    multi_select: bool = False


class SubagentEvent(BaseModel):
    """Progress of an Agent tool call, so UIs can show what the subagent is doing."""

    type: Literal["subagent"] = "subagent"
    label: str
    subagent_type: str
    status: Literal["queued", "started", "step", "finished"]
    detail: str = ""  # step: tool name; finished: ok | error | cancelled


class UsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    context_tokens: int
    context_limit: int


class CompactionEvent(BaseModel):
    """Context was compacted before the next model call."""

    type: Literal["compaction"] = "compaction"
    tokens_before: int
    tokens_after: int
    stages: list[str] = Field(default_factory=list)  # think | microcompact | summary


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    stop_reason: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: int
    message: str


StreamEvent = Annotated[
    TokenEvent
    | ToolCallEvent
    | ToolResultEvent
    | ApprovalRequiredEvent
    | QuestionEvent
    | SubagentEvent
    | UsageEvent
    | CompactionEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
