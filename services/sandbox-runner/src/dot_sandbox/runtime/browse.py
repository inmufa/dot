"""Read-only workspace views for the UI: tree, raw bytes, recent files, stat."""

import os
from pathlib import Path

from dot_sandbox.errors import SandboxError
from dot_sandbox.jail import inside

HIDDEN = frozenset({".dot", ".git", "__pycache__", "node_modules", ".venv"})
MAX_ENTRIES = 1000
MAX_DEPTH = 4


def visible(root: Path, path: Path) -> bool:
    """False for `.dot` and other noise anywhere on the path below root."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return not any(p in HIDDEN for p in parts)


def _entry(root: Path, p: Path, depth_info: bool = False) -> dict[str, object] | None:
    try:
        st = p.lstat()
    except OSError:
        return None
    is_link = p.is_symlink()
    if is_link and not inside(root, p):
        return None  # a link out of the workspace is not shown
    is_dir = p.is_dir()
    return {
        "path": str(p),
        "name": p.name,
        "type": "dir" if is_dir else "file",
        "size": None if is_dir else (p.stat().st_size if is_link else st.st_size),
        "modified": st.st_mtime,
    }


def tree(root: Path, base: Path, depth: int) -> list[dict[str, object]]:
    root = root.resolve()
    if not base.is_dir():
        raise SandboxError(404, "not_found", "no such directory")
    if not visible(root, base):
        raise SandboxError(404, "not_found", "no such directory")
    out: list[dict[str, object]] = []
    stack = [(base, 1)]
    while stack and len(out) < MAX_ENTRIES:
        folder, level = stack.pop(0)
        try:
            children = sorted(
                folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            continue
        for child in children:
            if child.name in HIDDEN or len(out) >= MAX_ENTRIES:
                continue
            e = _entry(root, child)
            if e is None:
                continue
            out.append(e)
            if (
                e["type"] == "dir"
                and level < min(depth, MAX_DEPTH)
                and not child.is_symlink()
            ):
                stack.append((child, level + 1))
    return out


def read_raw(root: Path, path: Path, max_bytes: int) -> bytes:
    root = root.resolve()
    if not visible(root, path) or not path.is_file():
        raise SandboxError(404, "not_found", "no such file")
    size = path.stat().st_size
    if size > max_bytes:
        raise SandboxError(413, "too_large", f"{size} bytes exceeds {max_bytes}")
    with path.open("rb") as fh:
        return fh.read(max_bytes + 1)[:max_bytes]


def recent(root: Path, since: float, limit: int) -> list[dict[str, object]]:
    """Files modified at or after `since` (epoch s), newest first, noise skipped."""
    root = root.resolve()
    found: list[tuple[float, Path]] = []
    for dirpath, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in HIDDEN]
        for n in names:
            p = Path(dirpath, n)
            try:
                mt = p.lstat().st_mtime
            except OSError:
                continue
            if mt >= since and not p.is_symlink():
                found.append((mt, p))
    found.sort(reverse=True)
    return [e for _, p in found[:limit] if (e := _entry(root, p))]


def stat_many(root: Path, paths: list[str]) -> list[dict[str, object]]:
    root = root.resolve()
    out = []
    for raw in paths[:500]:
        p = Path(raw)
        if not p.is_absolute():
            p = root / p
        try:
            real = p.resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if real.is_relative_to(root) and real.is_file() and visible(root, real):
            if e := _entry(root, real):
                out.append(e)
    return out
