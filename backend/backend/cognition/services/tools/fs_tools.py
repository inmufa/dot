"""Read, Write, Edit, Glob, Grep mapped onto the sandbox /fs/* endpoints."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.engine.images import is_image_path
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


async def _read_image(ctx: ToolContext, path: str) -> ToolResult:
    name = path.rsplit("/", 1)[-1]
    if ctx.images is None or not await ctx.images.enabled():
        return ToolResult(
            call_id="",
            output=f"Cannot view {name}: the model has no vision enabled. "
            "Tell the user you cannot see images.",
            is_error=True,
        )
    if await ctx.images.load(ctx.session_id, path) is None:
        return ToolResult(
            call_id="", output=f"Cannot read {name} as an image.", is_error=True
        )
    # Image text is untrusted, like any file content from outside the user's prompt.
    return ToolResult(
        call_id="",
        output=f"[image: {name}] The picture follows in the next message.",
        tainted=True,
        image_path=path,
    )


async def run_read(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    path = abs_path(ctx, a["file_path"])
    if path and is_image_path(path):
        return await _read_image(ctx, path)
    payload = {
        "path": path,
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


def _op(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "old": str(e.get("old_string", "")),
        "new": str(e.get("new_string", "")),
        "replace_all": bool(e.get("replace_all", False)),
    }


async def run_edit(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    payload: dict[str, Any] = {"path": abs_path(ctx, a["file_path"])}
    edits = a.get("edits")
    if isinstance(edits, list) and edits:
        payload["edits"] = [_op(e) for e in edits if isinstance(e, dict)]
    elif "old_string" in a:
        payload.update(_op(a))
    else:
        return ToolResult(
            call_id="",
            output="Edit needs old_string + new_string, or an edits list.",
            is_error=True,
        )
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
            description=(
                "Read a text file (line numbers) or an image. Big file: Grep for the "
                "spot first, then Read with offset/limit around it. Do not re-read "
                "a file already in context unless it changed."
            ),
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
            description=(
                "Create a new file, or replace most of an existing one (Read it "
                "first). For a few changes in an existing file use Edit."
            ),
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
                "Replace exact text in a file you have Read. old_string must match "
                "the file byte for byte (indentation too, without the line-number "
                "prefix) and be unique unless replace_all. Several changes in one "
                "file: pass edits=[{old_string, new_string, replace_all?}, ...] in "
                "one call; they apply in order, all or nothing."
            ),
            input_schema=_schema(
                {
                    "file_path": _S,
                    "old_string": _S,
                    "new_string": _S,
                    "replace_all": {"type": "boolean"},
                    "edits": {
                        "type": "array",
                        "items": _schema(
                            {
                                "old_string": _S,
                                "new_string": _S,
                                "replace_all": {"type": "boolean"},
                            },
                            ["old_string", "new_string"],
                        ),
                    },
                },
                ["file_path"],
            ),
        ),
        run_edit,
    ),
    Tool(
        ToolDefinition(
            name="Glob",
            mutating=False,
            description=(
                "Find files by name pattern (e.g. '**/*.py', 'src/**/config*'), "
                "newest first. Use it when you know the name, not the content."
            ),
            input_schema=_schema({"pattern": _S, "path": _S}, ["pattern"]),
        ),
        run_glob,
    ),
    Tool(
        ToolDefinition(
            name="Grep",
            mutating=False,
            description=(
                "Regex search inside files (ripgrep). output_mode: "
                "files_with_matches (default, which files), content (matching "
                "lines with numbers; add context for surrounding lines), count. "
                "Narrow with glob (e.g. '*.ts') or path."
            ),
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
