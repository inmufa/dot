from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from dot_contracts.permissions import ClassifierVerdict
from dot_contracts.tools import ToolInvocation, ToolResult
from dot_contracts.ui.effort import EffortInfo


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
    # Ask form (F9): when set, answer with `values` instead of `selected`.
    title: str | None = None
    fields: list[dict[str, Any]] | None = None


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
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_ms: int | None = None  # this model step
    tokens_per_s: float | None = None
    effort: EffortInfo | None = None


class WidgetEvent(BaseModel):
    """Present tool: a display widget. Also stored in the tool call arguments."""

    type: Literal["widget"] = "widget"
    call_id: str
    kind: str
    title: str | None = None
    props: dict[str, Any]


class SourceItem(BaseModel):
    n: int  # citation number, stable within the session turn
    title: str
    url: str
    snippet: str | None = None


class SourcesEvent(BaseModel):
    """Web results the turn has seen so far (research citations)."""

    type: Literal["sources"] = "sources"
    call_id: str
    sources: list[SourceItem]


class InjectedEvent(BaseModel):
    """A message the user sent mid-turn joined the running turn before the next model call."""

    type: Literal["injected"] = "injected"
    text: str


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
    | WidgetEvent
    | SourcesEvent
    | CompactionEvent
    | InjectedEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
