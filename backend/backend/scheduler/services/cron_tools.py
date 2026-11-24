"""CronCreate / CronList / CronDelete (deferred). Create and delete need approval."""

from typing import Any

from dot_contracts.schedules import ScheduleInfo
from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.core.exceptions import DomainException
from backend.core.text import strip_control_tags
from backend.scheduler.services.jobs import JobService

_S = {"type": "string"}


def _err(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True)


def _line(j: ScheduleInfo) -> str:
    state = "on" if j.enabled else "off"
    nxt = j.next_run_at.isoformat(timespec="minutes") if j.next_run_at else "-"
    prompt = " ".join(strip_control_tags(j.prompt).split())[:120]
    return f"[{j.id}] {j.kind} {state} '{j.cron}' next {nxt}: {prompt}"


def make_cron_tools(jobs: JobService) -> list[Tool]:
    async def create(_c: ToolContext, a: dict[str, Any]) -> ToolResult:
        try:
            info = await jobs.create(
                str(a["cron"]),
                str(a["prompt"]),
                enabled=a.get("enabled", True) is not False,
            )
        except DomainException as exc:
            reason = exc.ctx.get("reason", "")
            return _err(f"Cannot create the job (error {exc.code}) {reason}".strip())
        return ToolResult(call_id="", output=f"Created {_line(info)}")

    async def list_(_c: ToolContext, _a: dict[str, Any]) -> ToolResult:
        rows = await jobs.all()
        text = "\n".join(_line(j) for j in rows) or "(no scheduled jobs)"
        return ToolResult(
            call_id="", output=text, tainted=any(j.kind == "user" for j in rows)
        )

    async def delete(_c: ToolContext, a: dict[str, Any]) -> ToolResult:
        try:
            await jobs.delete(str(a["id"]))
        except DomainException as exc:
            return _err(f"Cannot delete the job (error {exc.code})")
        return ToolResult(call_id="", output=f"Deleted job {a['id']}")

    def spec(
        name: str, desc: str, props: dict, req: list[str], *, mutating: bool
    ) -> ToolDefinition:
        # A job outlives the session that made it: a prompt-injected model must
        # not persist work without the user's say (every mode except bypass).
        return ToolDefinition(
            name=name,
            description=desc,
            deferred=True,
            mutating=mutating,
            needs_approval=mutating,
            input_schema={"type": "object", "properties": props, "required": req},
        )

    return [
        Tool(
            spec(
                "CronCreate",
                "Schedule a prompt to run in a fresh session on a 5-field cron "
                "expression (minute hour day month weekday). Runs need the same "
                "approvals as any session.",
                {"cron": _S, "prompt": _S, "enabled": {"type": "boolean"}},
                ["cron", "prompt"],
                mutating=True,
            ),
            create,
        ),
        Tool(
            spec(
                "CronList",
                "List scheduled jobs and their next run.",
                {},
                [],
                mutating=False,
            ),
            list_,
        ),
        Tool(
            spec(
                "CronDelete",
                "Delete a scheduled job by id.",
                {"id": _S},
                ["id"],
                mutating=True,
            ),
            delete,
        ),
    ]
