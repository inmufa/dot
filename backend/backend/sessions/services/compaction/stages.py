"""Pure, cheap compaction stages. Each returns {seq: new model-visible text}."""

import json
import posixpath
import re

from backend.sessions.models import Message

THINK_KEEP_TURNS = 4
_THINK = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


def strip_think(text: str) -> str:
    return _THINK.sub("", text).strip()


def _turn_age(rows: list[Message]) -> dict[int, int]:
    """seq -> number of user turns that came after the row."""
    age, later = {}, 0
    for row in reversed(rows):
        age[row.seq] = later
        if row.role == "user":
            later += 1
    return age


def drop_old_think(rows: list[Message]) -> dict[int, str]:
    """Stage a: `<think>` content of assistant messages older than 4 turns."""
    age = _turn_age(rows)
    out: dict[int, str] = {}
    for row in rows:
        if row.role != "assistant" or age[row.seq] < THINK_KEEP_TURNS:
            continue
        text = row.model_text
        if "<think>" in text:
            out[row.seq] = strip_think(text)
    return out


def norm_path(path: str, workspace: str) -> str:
    full = path if path.startswith("/") else f"{workspace.rstrip('/')}/{path}"
    return posixpath.normpath(full)


def read_paths(rows: list[Message], workspace: str) -> dict[str, str]:
    """call id -> normalised path, for every Read call in `rows`."""
    paths: dict[str, str] = {}
    for row in rows:
        if row.role != "assistant":
            continue
        for call in row.tool_calls or []:
            fn = call.get("function") or {}
            if fn.get("name") != "Read":
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                continue
            if isinstance(args, dict) and isinstance(args.get("file_path"), str):
                paths[str(call.get("id"))] = norm_path(args["file_path"], workspace)
    return paths


def microcompact(rows: list[Message], workspace: str) -> dict[int, str]:
    """Stage b: keep only the latest Read result of each file."""
    by_call = read_paths(rows, workspace)
    latest: dict[str, int] = {}
    reads: list[tuple[Message, str]] = []
    for row in rows:
        path = by_call.get(row.tool_call_id or "") if row.role == "tool" else None
        if path:
            reads.append((row, path))
            latest[path] = row.seq
    out: dict[int, str] = {}
    for row, path in reads:
        if row.seq == latest[path]:
            continue
        stub = (
            f"[Earlier Read of {path} omitted: a newer Read of this file "
            "appears later in the conversation.]"
        )
        if row.model_text != stub and len(row.model_text) > len(stub):
            out[row.seq] = stub
    return out
