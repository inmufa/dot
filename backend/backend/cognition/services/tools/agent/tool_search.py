"""ToolSearch: find deferred tools (BM25 or `select:A,B`) and activate them."""

import json
from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.skills.bm25 import Bm25, tokenize
from backend.cognition.services.tools.registry import (
    Tool,
    ToolContext,
    ToolRegistry,
    schema_of,
)

SEARCH_MAX_CHARS = 30_000
_NAME_WEIGHT = 3  # name tokens count more than description tokens
_LIMIT = 10


def rank(defs: list[ToolDefinition], query: str, limit: int) -> list[str]:
    docs = {
        d.name: tokenize(d.name) * _NAME_WEIGHT + tokenize(d.description) for d in defs
    }
    scores = Bm25(docs).scores(tokenize(query))
    order = sorted(scores, key=lambda n: (-scores[n], n))
    return order[:limit]


def _render(defs: dict[str, ToolDefinition], names: list[str]) -> str:
    return "\n".join(
        f'<tool name="{n}">{json.dumps(schema_of(defs[n])["function"])}</tool>'
        for n in names
    )


def make_tool_search(registry: ToolRegistry) -> Tool:
    async def run(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        defs = {d.name: d for d in registry.definitions() if d.deferred}
        query = str(a["query"]).strip()
        if query.lower().startswith("select:"):
            wanted = [n.strip() for n in query[7:].split(",") if n.strip()]
            found = [n for n in wanted if n in defs]
            missing = [n for n in wanted if n not in defs]
        else:
            raw = a.get("max_results", 5)
            limit = max(1, min(raw if isinstance(raw, int) else 5, _LIMIT))
            found, missing = rank(list(defs.values()), query, limit), []
        if not found:
            names = ", ".join(defs) or "(none)"
            hint = f" Not found: {', '.join(missing)}." if missing else ""
            return ToolResult(
                call_id="",
                output=f"No matching deferred tools.{hint} Available: {names}",
                is_error=bool(missing),
            )
        if ctx.agent is not None:
            ctx.agent.activations.activate(ctx.session_id, found)
        text = f"Activated {len(found)} tool(s); call them from your next step.\n"
        text += _render(defs, found)
        if missing:
            text += f"\nNot found: {', '.join(missing)}"
        return ToolResult(call_id="", output=text)

    definition = ToolDefinition(
        name="ToolSearch",
        mutating=False,
        description=(
            "Load deferred tools. query is keywords, or 'select:Name1,Name2' for "
            "exact names. Matching tools become callable on your next step."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    )
    return Tool(definition, run, max_chars=SEARCH_MAX_CHARS)
