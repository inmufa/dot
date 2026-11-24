"""TaskCreate, TaskUpdate, TaskList, TaskGet over the SQLite task DAG."""

from typing import Any

from dot_contracts.tasks import TaskInfo
from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tasks.task_service import (
    TASK_NOT_FOUND,
    TaskError,
    TaskPatch,
)
from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.core.exceptions import DomainException

_STATUS = {"type": "string", "enum": ["pending", "in_progress", "completed"]}
_IDS = {"type": "array", "items": {"type": "string"}}


def _line(t: TaskInfo) -> str:
    waits = f" blocked_by={','.join(t.blocked_by)}" if t.blocked_by else ""
    return f"{t.id} [{t.status}] {t.subject}{waits}"


def _detail(t: TaskInfo) -> str:
    return f"{_line(t)}\n{t.description}".rstrip()


def _fail(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True)


def _ids(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TaskError("blocked_by must be a list of task ids")  # noqa: EM101
    return value


async def _guard(ctx: ToolContext, work) -> ToolResult:
    if ctx.agent is None:
        return _fail("Tasks are not available.")
    try:
        return ToolResult(call_id="", output=await work(ctx.agent.tasks))
    except TaskError as exc:
        return _fail(f"Task error: {exc}")
    except DomainException as exc:
        if exc.code == TASK_NOT_FOUND:
            return _fail("Task error: no task with that id (use TaskList).")
        raise


async def run_create(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    async def work(svc) -> str:
        blockers = _ids(a.get("blocked_by"))
        t = await svc.create(
            ctx.session_id, a["subject"], a.get("description", ""), blockers
        )
        return f"Created {_line(t)}"

    return await _guard(ctx, work)


async def run_update(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    async def work(svc) -> str:
        patch = TaskPatch(
            a.get("subject"),
            a.get("description"),
            a.get("status"),
            _ids(a.get("blocked_by")),
        )
        return f"Updated {_line(await svc.update(ctx.session_id, a['task_id'], patch))}"

    return await _guard(ctx, work)


async def run_list(ctx: ToolContext, _a: dict[str, Any]) -> ToolResult:
    async def work(svc) -> str:
        tasks = await svc.list_tasks(ctx.session_id)
        return "\n".join(_line(t) for t in tasks) or "(no tasks)"

    return await _guard(ctx, work)


async def run_get(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    async def work(svc) -> str:
        return _detail(await svc.get(ctx.session_id, a["task_id"]))

    return await _guard(ctx, work)


def _tool(name: str, desc: str, props: dict, required: list[str], run) -> Tool:
    schema = {"type": "object", "properties": props, "required": required}
    definition = ToolDefinition(
        name=name, description=desc, input_schema=schema, mutating=False
    )
    return Tool(definition, run)


TASK_TOOLS = [
    _tool(
        "TaskCreate",
        "Add a task to the session plan. blocked_by lists task ids that must finish first.",
        {
            "subject": {"type": "string"},
            "description": {"type": "string"},
            "blocked_by": _IDS,
        },
        ["subject"],
        run_create,
    ),
    _tool(
        "TaskUpdate",
        "Change a task: status (pending/in_progress/completed), subject, "
        "description or blocked_by. A blocked task cannot start.",
        {
            "task_id": {"type": "string"},
            "status": _STATUS,
            "subject": {"type": "string"},
            "description": {"type": "string"},
            "blocked_by": _IDS,
        },
        ["task_id"],
        run_update,
    ),
    _tool("TaskList", "List all tasks with status and blockers.", {}, [], run_list),
    _tool(
        "TaskGet",
        "Show one task in full.",
        {"task_id": {"type": "string"}},
        ["task_id"],
        run_get,
    ),
]
