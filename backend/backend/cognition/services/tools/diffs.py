"""Diffs shown on approval cards."""

import difflib
from typing import Any

from backend.cognition.services.tools.fs_tools import abs_path
from backend.cognition.services.tools.registry import ToolContext

MAX_DIFF_CHARS = 20_000


def _hunk(old_text: Any, new_text: Any) -> list[str]:
    old = str(old_text or "").splitlines()
    new = str(new_text or "").splitlines()
    return [*(f"- {x}" for x in old), *(f"+ {x}" for x in new)]


def edit_diff(args: dict[str, Any]) -> str:
    edits = args.get("edits")
    if isinstance(edits, list) and edits:
        parts = [
            "\n".join(_hunk(e.get("old_string"), e.get("new_string")))
            for e in edits
            if isinstance(e, dict)
        ]
        return "\n...\n".join(parts)[:MAX_DIFF_CHARS]
    return "\n".join(_hunk(args.get("old_string"), args.get("new_string")))


async def write_diff(ctx: ToolContext, args: dict[str, Any]) -> str | None:
    """Unified diff of a Write against the file's current content (if any)."""
    path = abs_path(ctx, str(args.get("file_path", "")))
    if not path:
        return None
    r = await ctx.sandbox.post(ctx.session_id, "/internal/peek", {"path": path})
    if not r.ok:
        return None
    exists, old = bool(r.data.get("exists")), r.data.get("content")
    if exists and old is None:
        return "(existing file is binary or too large to diff)"
    lines = difflib.unified_diff(
        (old or "").splitlines(),
        str(args.get("content", "")).splitlines(),
        fromfile=path if exists else "/dev/null",
        tofile=path,
        lineterm="",
    )
    text = "\n".join(lines)
    return text[:MAX_DIFF_CHARS] + ("\n..." if len(text) > MAX_DIFF_CHARS else "")


async def approval_diff(
    ctx: ToolContext, name: str, args: dict[str, Any]
) -> str | None:
    if name == "Edit":
        return edit_diff(args)
    if name == "Write":
        return await write_diff(ctx, args)
    return None
