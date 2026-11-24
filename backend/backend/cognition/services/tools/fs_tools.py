"""Read, Write, Edit, Glob, Grep mapped onto the sandbox /fs/* endpoints."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.routing.clients.sandbox_client import SandboxResponse

READ_MAX_CHARS = 20_000
_HINTS = {"read_required": " Use Read on this file first, then retry."}


def abs_path(ctx: ToolContext, path: str | None) -> str | None:
    if not path:
        return None
    return path if path.startswith("/") else f"{ctx.workspace.rstrip('/')}/{path}"


def fail(resp: SandboxResponse) -> ToolResult:
    text = resp.error_text() + _HINTS.get(str(resp.data.get("error")), "")
    return ToolResult(call_id="", output=text, is_error=True)


def ok(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text)


async def _call(
    ctx: ToolContext, path: str, payload: dict[str, Any]
) -> SandboxResponse:
    return await ctx.sandbox.post(ctx.session_id, path, payload)


async def run_read(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    payload = {
        "path": abs_path(ctx, a["file_path"]),
        "offset": a.get("offset", 0),
        "limit": a.get("limit", 2000),
    }
    r = await _call(ctx, "/fs/read", payload)
    if not r.ok:
        return fail(r)
    total = r.data.get("total_lines", 0)
    return ok(f"{r.data.get('content', '')}\n[total_lines: {total}]")


async def run_write(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    payload = {"path": abs_path(ctx, a["file_path"]), "content": a["content"]}
    r = await _call(ctx, "/fs/write", payload)
    if not r.ok:
        return fail(r)
    verb = "Created" if r.data.get("created") else "Overwrote"
    return ok(f"{verb} {r.data.get('path')}")


async def run_edit(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    payload = {
        "path": abs_path(ctx, a["file_path"]),
        "old": a["old_string"],
        "new": a["new_string"],
        "replace_all": a.get("replace_all", False),
    }
    r = await _call(ctx, "/fs/edit", payload)
    if not r.ok:
        return fail(r)
    text = f"Edited {r.data.get('path')} ({r.data.get('replacements')} replacement(s))"
    if r.data.get("lint"):
        text += f"\nLint:\n{r.data['lint']}"
    return ok(text)


async def run_glob(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    payload = {"pattern": a["pattern"], "path": abs_path(ctx, a.get("path"))}
    r = await _call(ctx, "/fs/glob", payload)
    if not r.ok:
        return fail(r)
    return ok("\n".join(r.data.get("paths", [])) or "(no matches)")


async def run_grep(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    payload = {
        "pattern": a["pattern"],
        "path": abs_path(ctx, a.get("path")),
        "glob": a.get("glob"),
        "output_mode": a.get("output_mode", "files_with_matches"),
        "context": a.get("context", 0),
        "ignore_case": a.get("ignore_case", False),
        "head_limit": a.get("head_limit", 250),
    }
    r = await _call(ctx, "/fs/grep", payload)
    if not r.ok:
        return fail(r)
    return ok(r.data.get("output") or "(no matches)")


def _schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


_S = {"type": "string"}
_I = {"type": "integer"}

FS_TOOLS = [
    Tool(
        ToolDefinition(
            name="Read",
            mutating=False,
            description="Read a file with line numbers. Use offset/limit for big files.",
            input_schema=_schema(
                {"file_path": _S, "offset": _I, "limit": _I}, ["file_path"]
            ),
        ),
        run_read,
        max_chars=READ_MAX_CHARS,
    ),
    Tool(
        ToolDefinition(
            name="Write",
            description="Create or overwrite a file. Existing files must be Read first.",
            input_schema=_schema(
                {"file_path": _S, "content": _S}, ["file_path", "content"]
            ),
        ),
        run_write,
    ),
    Tool(
        ToolDefinition(
            name="Edit",
            description=(
                "Replace exact text in a file (Read it first). old_string must be "
                "unique unless replace_all is true."
            ),
            input_schema=_schema(
                {
                    "file_path": _S,
                    "old_string": _S,
                    "new_string": _S,
                    "replace_all": {"type": "boolean"},
                },
                ["file_path", "old_string", "new_string"],
            ),
        ),
        run_edit,
    ),
    Tool(
        ToolDefinition(
            name="Glob",
            mutating=False,
            description="Find files by glob pattern, newest first.",
            input_schema=_schema({"pattern": _S, "path": _S}, ["pattern"]),
        ),
        run_glob,
    ),
    Tool(
        ToolDefinition(
            name="Grep",
            mutating=False,
            description="Regex search in files (ripgrep semantics).",
            input_schema=_schema(
                {
                    "pattern": _S,
                    "path": _S,
                    "glob": _S,
                    "output_mode": {
                        "type": "string",
                        "enum": ["files_with_matches", "content", "count"],
                    },
                    "context": _I,
                    "ignore_case": {"type": "boolean"},
                    "head_limit": _I,
                },
                ["pattern"],
            ),
        ),
        run_grep,
    ),
]
