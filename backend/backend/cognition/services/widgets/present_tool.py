"""Present: show a widget in the chat. Display only, never blocks."""

import json
from typing import Any

from dot_contracts.events import WidgetEvent
from dot_contracts.tools import ToolDefinition, ToolResult
from pydantic import ValidationError

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.widgets.models import (
    EXAMPLES,
    KINDS,
    MAX_JSON_CHARS,
    MODELS,
    explain,
)
from backend.cognition.services.widgets.sanitize import clean

DESCRIPTION = (
    "Show a data table or chart in the chat (display only). Never for prose or articles. "
    "kind and props: table {columns:[text], rows:[[text]]}; "
    "chart {type:bar|line|area|pie, labels:[text], series:[{name, values:[number]}]}; "
    "also stats, steps, checklist, cards, callout, tabs, accordion, choices "
    "(errors show the exact shape). Plain text only, no HTML."
)


class WidgetError(ValueError):
    """A Present call the model must fix and resend."""


def validate_present(args: dict[str, Any]) -> tuple[str, str | None, dict[str, Any]]:
    """(kind, title, clean props) or WidgetError with a model-readable reason."""
    kind = args.get("kind")
    if kind not in KINDS:
        msg = f"kind must be one of {', '.join(KINDS)}"
        raise WidgetError(msg)
    props = args.get("props")
    if not isinstance(props, dict):
        msg = f"props must be an object shaped for kind '{kind}'"
        raise WidgetError(msg)
    try:
        if len(json.dumps(props, allow_nan=True)) > MAX_JSON_CHARS:
            msg = f"props are too large (max {MAX_JSON_CHARS} chars); show less"
            raise WidgetError(msg)
    except (TypeError, ValueError, RecursionError) as exc:
        msg = "props are not plain JSON"
        raise WidgetError(msg) from exc
    title = args.get("title")
    if title is not None and not isinstance(title, str):
        msg = "title must be a string"
        raise WidgetError(msg)
    try:
        clean_title = clean(title, 120) if title else None
    except ValueError as exc:
        msg = f"title {exc}"
        raise WidgetError(msg) from exc
    try:
        model = MODELS[kind].model_validate(props)
    except ValidationError as exc:
        msg = (
            f"props for '{kind}' are invalid: {explain(exc)}. "
            f"Correct shape: {EXAMPLES[kind]}. For long text, skip Present and answer in markdown."
        )
        raise WidgetError(msg) from exc
    return kind, clean_title, model.model_dump(mode="json", exclude_none=True)


async def run_present(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    try:
        kind, title, props = validate_present(a)
    except WidgetError as exc:
        return ToolResult(call_id="", output=f"Invalid widget: {exc}", is_error=True)
    if ctx.emit is not None:
        ctx.emit(WidgetEvent(call_id=ctx.call_id, kind=kind, title=title, props=props))
    return ToolResult(call_id="", output=f"Shown to the user: {kind}.")


PRESENT_TOOL = Tool(
    ToolDefinition(
        name="Present",
        mutating=False,
        description=DESCRIPTION,
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(KINDS)},
                "title": {"type": "string"},
                "props": {"type": "object"},
            },
            "required": ["kind", "props"],
        },
    ),
    run_present,
)
