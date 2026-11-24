"""DOT.md loading with `@path` includes (workspace only, depth 3, cycle-safe)."""

import posixpath
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from backend.core.text import strip_control_tags

Reader = Callable[[str], Awaitable[str | None]]
MAX_DEPTH = 3
_INCLUDE = re.compile(r"^@(\S+)\s*$")
_FENCE = "```"


@dataclass
class _Walk:
    read: Reader
    root: str
    visited: set[str] = field(default_factory=set)
    budget: int = 0  # characters still allowed


def inside(root: str, path: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def resolve_include(root: str, base: str, target: str) -> str | None:
    """Absolute path of `@target` from file `base`, or None when it leaves the workspace."""
    if target.startswith("~"):
        return None
    joined = (
        target
        if target.startswith("/")
        else posixpath.join(posixpath.dirname(base), target)
    )
    path = posixpath.normpath(joined)
    return path if inside(root, path) and path != root else None


async def _expand(walk: _Walk, path: str, depth: int, chain: tuple[str, ...]) -> str:
    text = await walk.read(path)
    if text is None:
        return ""
    walk.visited.add(path)
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        match = None if fenced else _INCLUDE.match(line.strip())
        if match is None:
            out.append(line)
        else:
            out.append(await _include(walk, path, match[1], depth, chain))
        if sum(map(len, out)) > walk.budget:
            break  # the caller truncates; stop reading more files
    return "\n".join(out)


async def _include(
    walk: _Walk, base: str, target: str, depth: int, chain: tuple[str, ...]
) -> str:
    path = resolve_include(walk.root, base, target)
    if path is None:
        return f"[include skipped: {target} is outside the workspace]"
    if path in chain:
        return f"[include skipped: {target} is a cycle]"
    if path in walk.visited:
        return f"[include skipped: {target} already included]"
    if depth >= MAX_DEPTH:
        return f"[include skipped: {target} is nested deeper than {MAX_DEPTH}]"
    body = await _expand(walk, path, depth + 1, (*chain, path))
    if not body:
        return f"[include skipped: {target} not found]"
    rel = path[len(walk.root.rstrip("/")) + 1 :]
    return f"[begin include {rel}]\n{body}\n[end include {rel}]"


def clip(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    return text[:cap].rstrip() + f"\n[truncated: {len(text) - cap} more characters]"


async def load_dotmd(read: Reader, root: str, path: str, cap: int) -> str | None:
    """Expanded, tag-stripped, size-capped text of a DOT.md; None when missing."""
    walk = _Walk(read, root, budget=cap * 2)
    text = await _expand(walk, path, 0, (path,))
    if not text.strip():
        return None
    return clip(strip_control_tags(text), cap)
