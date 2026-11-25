"""Ask: block until the user answers a question or a small form."""

import json
from typing import Any

from dot_contracts.events import QuestionEvent, QuestionOption
from dot_contracts.tools import ToolDefinition, ToolResult
from pydantic import ValidationError

from backend.cognition.services.interaction.questions import QUESTION_TIMEOUT
from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.widgets.forms import describe, parse_form
from backend.core.exceptions import DomainException

MIN_OPTIONS, MAX_OPTIONS = 2, 4
DESCRIPTION = (
    "Ask the user and wait for the answer. Quick question: question + options "
    "[{label, description}] (2-4), multi_select? . Form for several answers: "
    "fields [{id, type: single_select|multi_select|text|number|slider|toggle|date|rank, "
    "label, options?, min?, max?}]. Use it when you need a choice, not for chatting."
)


def _options(raw: Any) -> list[QuestionOption] | str:
    if not isinstance(raw, list) or not MIN_OPTIONS <= len(raw) <= MAX_OPTIONS:
        return f"options must be a list of {MIN_OPTIONS} to {MAX_OPTIONS} items"
    out = []
    for item in raw:
        if not isinstance(item, dict) or not str(item.get("label", "")).strip():
            return "every option needs a non-empty label"
        out.append(
            QuestionOption(
                label=str(item["label"]).strip(),
                description=str(item.get("description", "")),
            )
        )
    if len({o.label for o in out}) != len(out):
        return "option labels must be unique"
    return out


def _fail(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True)


async def _wait(ctx: ToolContext, qid: str, event: QuestionEvent) -> Any:
    assert ctx.agent is not None  # noqa: S101
    assert ctx.emit is not None  # noqa: S101
    try:
        ctx.emit(event)
        return await ctx.agent.questions.wait(qid, ctx.agent.question_timeout_s)
    except DomainException as exc:
        if exc.code != QUESTION_TIMEOUT:
            raise
        return None
    finally:
        ctx.agent.questions.discard(qid)


_TIMEOUT = "The user did not answer in time. Decide yourself or ask later."


async def _ask_form(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    assert ctx.agent is not None  # noqa: S101
    try:
        form = parse_form(a)
    except ValidationError as exc:
        return _fail(f"Invalid form: {describe(exc)}")
    fields = [f.model_dump(mode="json", exclude_none=True) for f in form.fields]
    qid = ctx.agent.questions.create(
        ctx.session_id, [], multi_select=False, fields=fields
    )
    event = QuestionEvent(
        question_id=qid,
        question=form.question or form.title or "",
        options=[],
        title=form.title,
        fields=fields,
    )
    answer = await _wait(ctx, qid, event)
    if answer is None:
        return _fail(_TIMEOUT)
    return ToolResult(
        call_id="",
        output="User submitted: " + json.dumps(answer.values, ensure_ascii=False),
    )


async def _ask_options(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    assert ctx.agent is not None  # noqa: S101
    options = _options(a.get("options"))
    if isinstance(options, str):
        return _fail(f"Invalid options: {options}")
    question = a.get("question")
    if not isinstance(question, str) or not question.strip():
        return _fail("Invalid arguments: question is required")
    multi = bool(a.get("multi_select", False))
    qid = ctx.agent.questions.create(
        ctx.session_id, [o.label for o in options], multi_select=multi
    )
    event = QuestionEvent(
        question_id=qid, question=question, options=options, multi_select=multi
    )
    answer = await _wait(ctx, qid, event)
    if answer is None:
        return _fail(_TIMEOUT)
    parts = []
    if answer.selected:
        parts.append("Selected: " + "; ".join(answer.selected))
    if answer.other:
        parts.append(f"Other (free text): {answer.other}")
    return ToolResult(call_id="", output="User answered. " + ". ".join(parts))


async def run_ask(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    if ctx.agent is None or ctx.emit is None:
        return _fail("Questions are not available here.")
    if a.get("fields") is not None:
        return await _ask_form(ctx, a)
    if a.get("options") is None:
        return _fail(
            "Invalid arguments: send options (quick question) or fields (form)"
        )
    return await _ask_options(ctx, a)


ASK_TOOL = Tool(
    ToolDefinition(
        name="Ask",
        mutating=False,
        description=DESCRIPTION,
        input_schema={
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["label"],
                    },
                },
                "multi_select": {"type": "boolean"},
                "title": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "object"}},
            },
        },
    ),
    run_ask,
)
