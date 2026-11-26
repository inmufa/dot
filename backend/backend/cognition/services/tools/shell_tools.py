"""Bash, BashOutput, KillShell mapped onto the sandbox /exec endpoints."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.fs_tools import abs_path, fail
from backend.cognition.services.tools.registry import Tool, ToolContext

DEFAULT_TIMEOUT_S = 120
_NET_MARKERS = (
    "curl",
    "wget",
    "http://",
    "https://",
    "git clone",
    "git pull",
    "git fetch",
    "pip ",
    "npm ",
    "pnpm ",
    "yarn ",
    "uv add",
    "uv sync",
    "apt",
    "ssh ",
    "scp ",
    "nc ",
    "ncat",
    "socat",
)


def _format_exec(d: dict[str, Any]) -> str:
    parts = []
    if d.get("stdout"):
        parts.append(d["stdout"].rstrip("\n"))
    if d.get("stderr"):
        parts.append("[stderr]\n" + d["stderr"].rstrip("\n"))
    if d.get("timed_out"):
        parts.append("[timed out]")
    if d.get("shell_id"):
        parts.append(f"[background shell_id: {d['shell_id']}]")
    if d.get("exit_code") is not None:
        parts.append(f"[exit code: {d['exit_code']}]")
    if d.get("spill_path"):
        parts.append(f"[full output saved at {d['spill_path']}]")
    return "\n".join(parts) or "(no output)"


async def run_bash(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    timeout = a.get("timeout_s", DEFAULT_TIMEOUT_S)
    payload = {
        "command": a["command"],
        "timeout_s": timeout,
        "cwd": abs_path(ctx, a.get("cwd")),
        "background": a.get("run_in_background", False),
    }
    r = await ctx.sandbox.post(ctx.session_id, "/exec", payload, timeout_s=timeout)
    if not r.ok:
        return fail(r)
    # Network-capable commands may bring in untrusted content (feeds the classifier).
    tainted = any(m in a["command"] for m in _NET_MARKERS)
    failed = r.data.get("exit_code") not in (0, None) or r.data.get("timed_out", False)
    return ToolResult(
        call_id="",
        output=_format_exec(r.data),
        is_error=bool(failed),
        tainted=tainted,
        spill_path=r.data.get("spill_path"),
    )


async def run_bash_output(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    r = await ctx.sandbox.post(
        ctx.session_id, "/exec/output", {"shell_id": a["shell_id"]}
    )
    if not r.ok:
        return fail(r)
    state = "running" if r.data.get("running") else "finished"
    body = _format_exec(r.data)
    return ToolResult(call_id="", output=f"[{state}]\n{body}", tainted=True)


async def run_kill(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    r = await ctx.sandbox.post(
        ctx.session_id, "/exec/kill", {"shell_id": a["shell_id"]}
    )
    if not r.ok:
        return fail(r)
    return ToolResult(call_id="", output=f"Killed shell {a['shell_id']}")


_SHELL = {"shell_id": {"type": "string"}}

SHELL_TOOLS = [
    Tool(
        ToolDefinition(
            name="Bash",
            description=(
                "Run a shell command: tests, builds, git, installs, and scripts. "
                "For repetitive or bulk work (many files, parsing data, math, "
                "loops) write one script instead of many tool calls. Keep output "
                "short (| tail, | head, counts). Servers or jobs over a minute: "
                "run_in_background, then poll with BashOutput."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_s": {"type": "integer"},
                    "cwd": {"type": "string"},
                    "run_in_background": {"type": "boolean"},
                },
                "required": ["command"],
            },
        ),
        run_bash,
    ),
    Tool(
        ToolDefinition(
            name="BashOutput",
            mutating=False,
            description="Read output of a background Bash shell.",
            input_schema={
                "type": "object",
                "properties": _SHELL,
                "required": ["shell_id"],
            },
        ),
        run_bash_output,
    ),
    Tool(
        ToolDefinition(
            name="KillShell",
            description="Kill a background Bash shell.",
            input_schema={
                "type": "object",
                "properties": _SHELL,
                "required": ["shell_id"],
            },
        ),
        run_kill,
    ),
]
