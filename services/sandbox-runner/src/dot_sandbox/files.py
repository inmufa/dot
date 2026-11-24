"""Read / write / edit / glob on jailed paths."""

import os
import stat
import tempfile
from pathlib import Path

from dot_sandbox.errors import SandboxError
from dot_sandbox.jail import inside
from dot_sandbox.runtime.state import ReadTracker

MAX_LINE = 2000
GLOB_MAX = 500
MAX_BYTES = 20_000_000
SKIP_DIRS = {".git"}


def _load(path: Path, max_bytes: int) -> str:
    if not path.exists():
        raise SandboxError(404, "not_found", f"{path} does not exist")
    if path.is_dir():
        raise SandboxError(400, "is_directory", f"{path} is a directory")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode):  # a FIFO would block the worker forever
        raise SandboxError(400, "not_regular", f"{path} is not a regular file")
    if st.st_size > max_bytes:
        raise SandboxError(413, "file_too_large", f"{path} exceeds {max_bytes} bytes")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SandboxError(422, "not_text", f"{path} is not valid UTF-8") from exc


def _split(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def read_file(
    tracker: ReadTracker,
    session: str,
    path: Path,
    offset: int,
    limit: int,
    max_bytes: int,
) -> tuple[str, int]:
    lines = _split(_load(path, max_bytes))
    window = lines[offset : offset + limit]
    out = []
    for i, line in enumerate(window, start=offset + 1):
        shown = (
            line if len(line) <= MAX_LINE else line[:MAX_LINE] + "... [line truncated]"
        )
        out.append(f"{i:6d}\t{shown}")
    tracker.mark(session, path)
    return "\n".join(out), len(lines)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".dot-tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        Path(tmp).chmod(mode)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_file(
    tracker: ReadTracker, session: str, path: Path, content: str, max_bytes: int
) -> bool:
    if path.is_dir():
        raise SandboxError(400, "is_directory", f"{path} is a directory")
    if len(content) > max_bytes:
        raise SandboxError(413, "file_too_large", f"content exceeds {max_bytes}")
    created = not path.exists()
    if not created:
        tracker.require(session, path)
    _atomic_write(path, content.encode("utf-8"))
    tracker.mark(session, path)
    return created


def edit_file(
    tracker: ReadTracker,
    session: str,
    path: Path,
    old: str,
    new: str,
    replace_all: bool,
) -> int:
    text = _load(path, MAX_BYTES)
    tracker.require(session, path)
    if old == new:
        raise SandboxError(422, "no_change", "old and new are identical")
    count = text.count(old) if old else 0
    if count == 0:
        raise SandboxError(422, "no_match", "old string not found")
    if count > 1 and not replace_all:
        raise SandboxError(422, "ambiguous", f"old string matches {count} times")
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    _atomic_write(path, updated.encode("utf-8"))
    tracker.mark(session, path)
    return count if replace_all else 1


def glob_files(root: Path, base: Path, pattern: str) -> list[str]:
    if not base.is_dir():
        raise SandboxError(404, "not_found", f"{base} is not a directory")
    if pattern.startswith("/") or ".." in Path(pattern).parts:
        raise SandboxError(400, "invalid_pattern", "pattern must be relative, no '..'")
    pat = pattern if "/" in pattern else f"**/{pattern}"
    found: list[tuple[int, str]] = []
    try:
        for p in base.glob(pat):
            if SKIP_DIRS & set(p.relative_to(base).parts):
                continue
            if not p.is_file() or not inside(root, p):
                continue
            found.append((p.stat().st_mtime_ns, str(p)))
    except (ValueError, NotImplementedError) as exc:
        raise SandboxError(400, "invalid_pattern", str(exc)) from exc
    except OSError:
        pass  # file vanished mid-walk; return what we have
    found.sort(key=lambda t: (-t[0], t[1]))
    return [p for _, p in found[:GLOB_MAX]]
