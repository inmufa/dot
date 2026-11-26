"""Memory tools. `Memory` writes outside the workspace, so it needs approval."""

from typing import Any

from dot_contracts.memory import MemoryFact, MemoryIn, MemoryKind, MemoryUpdate
from dot_contracts.tools import ToolDefinition, ToolResult
from pydantic import ValidationError

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.core.exceptions import DomainException
from backend.memory.services.store import MemoryService

_S = {"type": "string"}
_KINDS = [k.value for k in MemoryKind]
_PROPS: dict[str, Any] = {
    "id": _S,
    "name": _S,
    "description": _S,
    "kind": {"type": "string", "enum": _KINDS},
    "body": _S,
    "query": _S,
    "limit": {"type": "integer"},
}


def _line(f: MemoryFact) -> str:
    return f"[{f.id}] ({f.kind.value}) {f.name} - {f.description}".rstrip(" -")


def _full(f: MemoryFact) -> str:
    return f"{_line(f)}\n{f.body}"


def _err(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True)


async def _read(service: MemoryService, action: str, a: dict[str, Any]) -> ToolResult:
    raw = a.get("limit", 10)
    limit = min(max(raw if isinstance(raw, int) else 10, 1), 50)
    if action == "search":
        query = a.get("query")
        if not isinstance(query, str) or not query.strip():
            return _err("search needs a 'query'")
        facts = await service.search(query, limit)
        return ToolResult(
            call_id="",
            output="\n\n".join(_full(f) for f in facts) or "(no matching memories)",
            tainted=bool(facts),  # facts are model-written, maybe from web text
        )
    facts = await service.list_facts(limit)
    return ToolResult(
        call_id="",
        output="\n".join(_line(f) for f in facts) or "(memory is empty)",
        tainted=bool(facts),
    )


async def _write(service: MemoryService, action: str, a: dict[str, Any]) -> ToolResult:
    fields = {k: a[k] for k in ("name", "description", "kind", "body") if k in a}
    if action == "add":
        fact = await service.add(MemoryIn(**fields))
        return ToolResult(call_id="", output=f"Saved memory {_line(fact)}")
    fact_id = a.get("id")
    if not isinstance(fact_id, str):
        return _err(f"{action} needs an 'id'")
    if action == "delete":
        await service.delete(fact_id)
        return ToolResult(call_id="", output=f"Deleted memory {fact_id}")
    fact = await service.update(fact_id, MemoryUpdate(**fields))
    return ToolResult(call_id="", output=f"Updated memory {_line(fact)}")


def _runner(service: MemoryService, actions: frozenset[str]):
    async def run(_ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        action = a.get("action")
        if action not in actions:
            return _err(f"action must be one of: {', '.join(sorted(actions))}")
        try:
            if action in ("search", "list"):
                return await _read(service, action, a)
            return await _write(service, action, a)
        except ValidationError as exc:
            first = exc.errors()[0]
            return _err(f"Invalid memory field '{first['loc'][-1]}': {first['msg']}")
        except DomainException as exc:
            return _err(f"Memory error (code {exc.code})")

    return run


def make_memory_tools(service: MemoryService) -> list[Tool]:
    write = frozenset({"add", "update", "delete", "search", "list"})
    read = frozenset({"search", "list"})
    schema = {"type": "object", "properties": _PROPS, "required": ["action"]}
    return [
        Tool(
            ToolDefinition(
                name="Memory",
                mutating=True,  # writes ~/.dot/memory, outside the workspace
                description=(
                    "Save, update or delete long-term memory facts (one fact per "
                    "entry: name, description, body) or search them. action: "
                    "add | update | delete | search | list."
                ),
                input_schema={
                    **schema,
                    "properties": {
                        **_PROPS,
                        "action": {"type": "string", "enum": sorted(write)},
                    },
                },
            ),
            _runner(service, write),
        ),
        Tool(
            ToolDefinition(
                name="MemoryRecall",
                mutating=False,
                description="Search or list saved long-term memory facts. action: search | list.",
                input_schema={
                    **schema,
                    "properties": {
                        **_PROPS,
                        "action": {"type": "string", "enum": sorted(read)},
                    },
                },
            ),
            _runner(service, read),
        ),
    ]
