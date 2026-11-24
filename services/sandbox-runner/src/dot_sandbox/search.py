"""Grep: ripgrep when present, python fallback otherwise."""

import asyncio
import fnmatch
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from dot_sandbox.errors import SandboxError
from dot_sandbox.jail import inside
from dot_sandbox.runtime.env import scrubbed_env

MODES = {"files_with_matches", "content", "count"}
MAX_COLUMNS = 2000
RG_TIMEOUT_S = 60
MAX_GREP_FILE = 5_000_000


def _glob_ok(rel: str, glob: str | None) -> bool:
    if not glob:
        return True
    return fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(Path(rel).name, glob)


def _iter_files(root: Path, base: Path, glob: str | None) -> list[Path]:
    if base.is_file():
        return [base]
    out: list[Path] = []
    for dirpath, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(names):
            p = Path(dirpath) / name
            if _glob_ok(str(p.relative_to(base)), glob) and inside(root, p):
                out.append(p)
    return out


def _file_lines(p: Path) -> list[str] | None:
    try:
        st = p.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_GREP_FILE:
            return None
        data = p.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace").split("\n")


def _context_block(p: Path, lines: list[str], hits: list[int], ctx: int) -> list[str]:
    keep: set[int] = set()
    for h in hits:
        keep.update(range(max(0, h - ctx), min(len(lines), h + ctx + 1)))
    out: list[str] = []
    prev = -2
    for i in sorted(keep):
        if ctx and prev >= 0 and i != prev + 1:
            out.append("--")
        sep = ":" if i in hits else "-"
        out.append(f"{p}{sep}{i + 1}{sep}{lines[i]}")
        prev = i
    return out


def python_grep(
    root: Path, base: Path, regex: re.Pattern[str], q: "GrepQuery"
) -> list[str]:
    out: list[str] = []
    for p in _iter_files(root, base, q.glob):
        if len(out) >= q.head_limit:
            break
        lines = _file_lines(p)
        if lines is None:
            continue
        hits = [i for i, ln in enumerate(lines) if regex.search(ln)]
        if not hits:
            continue
        if q.mode == "files_with_matches":
            out.append(str(p))
        elif q.mode == "count":
            out.append(f"{p}:{len(hits)}")
        else:
            out.extend(_context_block(p, lines, hits, q.context))
    return out


async def _rg(base: Path, q: "GrepQuery") -> list[str]:
    """Stream rg output and stop at head_limit so huge results never sit in memory."""
    cmd = ["rg", "--no-heading", "--with-filename", "--color", "never"]
    cmd += ["--no-messages", "--max-columns", str(MAX_COLUMNS)]
    cmd += {"files_with_matches": ["-l"], "count": ["-c"], "content": ["-n"]}[q.mode]
    if q.mode == "content" and q.context:
        cmd += ["-C", str(q.context)]
    if q.ignore_case:
        cmd.append("-i")
    if q.glob:
        cmd += ["--glob", q.glob]
    cmd += ["-e", q.pattern, "--", str(base)]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        env=scrubbed_env(),
    )
    lines: list[str] = []
    try:
        async with asyncio.timeout(RG_TIMEOUT_S):
            if proc.stdout is None or proc.stderr is None:
                raise SandboxError(500, "internal", "rg pipes missing")
            async for raw in proc.stdout:
                lines.append(raw.decode("utf-8", "replace").rstrip("\n"))
                if len(lines) >= q.head_limit:
                    break
            else:
                await proc.wait()
                if proc.returncode not in (0, 1):
                    err = (await proc.stderr.read(2000)).decode("utf-8", "replace")
                    raise SandboxError(422, "bad_pattern", err.strip())
    except TimeoutError as exc:
        raise SandboxError(504, "grep_timeout", "grep timed out") from exc
    finally:
        if proc.returncode is None:
            proc.kill()
            # drain so asyncio sees the pipes close; wait() alone can hang
            await asyncio.wait_for(proc.communicate(), 5)
    return lines


@dataclass
class GrepQuery:
    pattern: str
    glob: str | None = None
    mode: str = "files_with_matches"
    context: int = 0
    ignore_case: bool = False
    head_limit: int = 250


async def grep(root: Path, base: Path, q: GrepQuery) -> str:
    if q.mode not in MODES:
        raise SandboxError(
            422, "bad_mode", f"output_mode must be one of {sorted(MODES)}"
        )
    if not await asyncio.to_thread(base.exists):
        raise SandboxError(404, "not_found", f"{base} does not exist")
    if shutil.which("rg"):
        lines = await _rg(base, q)
    else:
        try:  # python re only matters for the fallback; rg has its own syntax
            regex = re.compile(q.pattern, re.IGNORECASE if q.ignore_case else 0)
        except re.error as exc:
            raise SandboxError(422, "bad_pattern", str(exc)) from exc
        lines = await asyncio.to_thread(python_grep, root, base, regex, q)
    return "\n".join(lines[: q.head_limit])
