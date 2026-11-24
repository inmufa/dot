"""Path globs (gitignore style) and lexical path normalisation for rules."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RuleContext:
    workspace: str = "/workspace"
    home: str = field(default_factory=lambda: str(Path.home()))


def _glob_regex(pattern: str) -> str:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out.append("(?:/.*)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)


def normalise(raw: str, ctx: RuleContext) -> str:
    """Absolute lexical path (no symlink resolution) for a tool path argument."""
    raw = raw.strip()
    if raw == "~" or raw.startswith("~/"):
        raw = ctx.home + raw[1:]
    base = raw if raw.startswith("/") else f"{ctx.workspace.rstrip('/')}/{raw}"
    return re.sub(r"^/{2,}", "/", os.path.normpath(base))  # `//x` is `/x`


def path_matches(pattern: str, raw_path: str, ctx: RuleContext) -> bool:
    path = normalise(raw_path, ctx)
    ws = ctx.workspace.rstrip("/")
    rel = path[len(ws) + 1 :] if path.startswith(ws + "/") else None
    pat = pattern.strip()
    if pat == "~" or pat.startswith("~/"):
        pat = ctx.home + pat[1:]
    if pat.startswith("/"):
        return re.fullmatch(_glob_regex(pat) + "(?:/.*)?", path) is not None
    pat = pat.removeprefix("./")
    floating = "/" not in pat.rstrip("/") or pat.startswith("**")
    body = _glob_regex(pat.rstrip("/") or "**") + "(?:/.*)?"
    if floating and not pat.startswith("**"):
        body = "(?:.*/)?" + body
    candidates = [rel] if rel is not None else []
    if floating:
        candidates.append(path.lstrip("/"))
    return any(re.fullmatch(body, c) for c in candidates)
