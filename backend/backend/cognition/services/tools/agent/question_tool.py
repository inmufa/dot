"""AskUserQuestion: ask the user to pick from 2-4 options (plus free text)."""

from typing import Any

from dot_contracts.events import QuestionEvent, QuestionOption
from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.interaction.questions import QUESTION_TIMEOUT
from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.core.exceptions import DomainException

MIN_OPTIONS, MAX_OPTIONS = 2, 4


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


async def run_ask(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    options = _options(a.get("options"))
    if isinstance(options, str):
        return _fail(f"Invalid options: {options}")
    if ctx.agent is None or ctx.emit is None:
        return _fail("Questions are not available here.")
    multi = bool(a.get("multi_select", False))
    reg = ctx.agent.questions
    qid = reg.create(ctx.session_id, [o.label for o in options], multi_select=multi)
    try:
        ctx.emit(
            QuestionEvent(
                question_id=qid,
                question=str(a["question"]),
                options=options,
                multi_select=multi,
            )
        )
        answer = await reg.wait(qid, ctx.agent.question_timeout_s)
    except DomainException as exc:
        if exc.code != QUESTION_TIMEOUT:
            raise
        return _fail("The user did not answer in time. Decide yourself or ask later.")
    finally:
        reg.discard(qid)
    parts = []
    if answer.selected:
        parts.append("Selected: " + "; ".join(answer.selected))
    if answer.other:
        parts.append(f"Other (free text): {answer.other}")
    return ToolResult(call_id="", output="User answered. " + ". ".join(parts))


QUESTION_TOOL = Tool(
    ToolDefinition(
        name="AskUserQuestion",
        mutating=False,
        description=(
            "Ask the user a question with 2-4 options (label, description). "
            "The user may also type their own answer. Use when a choice is needed."
        ),
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
            },
            "required": ["question", "options"],
        },
    ),
    run_ask,
)
