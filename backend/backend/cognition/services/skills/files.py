"""Read-only access to files inside a skill directory, with jail checks."""

import os
from pathlib import Path

MAX_LISTED = 60
MAX_WALK = 5000  # directory entries inspected while listing
MAX_FILE_BYTES = 2_000_000
_SKIP = {"__pycache__", "node_modules", ".git"}


class SkillFileError(Exception):
    pass


def resolve_inside(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root`; refuse `..`, absolute paths and symlink escapes."""
    if not rel or "\x00" in rel:
        msg = "invalid file path"
        raise SkillFileError(msg)
    parts = Path(rel).parts
    if Path(rel).is_absolute() or ".." in parts:
        msg = "path must be relative and stay inside the skill directory"
        raise SkillFileError(msg)
    base = root.resolve()
    target = (base / rel).resolve()
    if not target.is_relative_to(base):
        msg = "path escapes the skill directory"
        raise SkillFileError(msg)
    if not target.is_file():
        msg = f"no such file in skill: {rel}"
        raise SkillFileError(msg)
    return target


def list_files(root: Path, limit: int = MAX_LISTED) -> list[str]:
    """Relative paths of regular files (SKILL.md excluded), sorted, capped.

    Symlinked directories are not entered; a symlinked file must stay inside.
    """
    base = root.resolve()
    out: list[str] = []
    seen = 0
    for dirpath, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP)
        for name in sorted(names):
            seen += 1
            p = Path(dirpath) / name
            rel = p.relative_to(base).as_posix()
            if rel != "SKILL.md" and p.is_file() and p.resolve().is_relative_to(base):
                out.append(rel)
        if seen > MAX_WALK or len(out) >= limit:
            break
    return sorted(out)[:limit]


def read_text(root: Path, rel: str, offset: int = 0, limit: int = 2000) -> str:
    """Numbered text lines like Read; binary files are refused."""
    path = resolve_inside(root, rel)
    if path.stat().st_size > MAX_FILE_BYTES:
        msg = "file is too large"
        raise SkillFileError(msg)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        msg = "binary file, cannot show it as text"
        raise SkillFileError(msg) from exc
    except OSError as exc:
        msg = "cannot read file"
        raise SkillFileError(msg) from exc
    chunk = lines[offset : offset + limit]
    body = "\n".join(f"{offset + i + 1}\t{ln}" for i, ln in enumerate(chunk))
    return f"{body}\n[total_lines: {len(lines)}]"
