"""Parsing helpers for llama-server output: think/tool_call tags, partial JSON."""

import json
import re
import uuid
from typing import Any

from backend.routing.clients.llm_types import ParsedToolCall

THINK_OPEN, THINK_CLOSE = "<think>", "</think>"
CALL_OPEN, CALL_CLOSE = "<tool_call>", "</tool_call>"
_FUNC_RE = re.compile(r"<function=([^>\s]+)>(.*?)(?:</function>|$)", re.DOTALL)
_PARAM_RE = re.compile(r"<parameter=([^>\s]+)>\n?(.*?)\n?</parameter>", re.DOTALL)
# Only repairs that never close an open string: a half-written value must not
# be silently accepted (e.g. a truncated Write content).
_REPAIRS = ("", "}", "]}")


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _hold(buf: str, tags: tuple[str, ...]) -> int:
    """Length of the longest buf suffix that is a proper prefix of any tag."""
    best = 0
    for tag in tags:
        for n in range(min(len(tag) - 1, len(buf)), best, -1):
            if tag.startswith(buf[-n:]):
                best = n
                break
    return best


class ContentFilter:
    """Splits streamed content into text, thinking and raw <tool_call> bodies."""

    def __init__(self) -> None:
        self.mode = "text"
        self.buf = ""
        self.calls: list[str] = []
        self._call = ""

    def feed(self, chunk: str) -> list[tuple[str, bool]]:
        self.buf += chunk
        out: list[tuple[str, bool]] = []
        while self._step(out):
            pass
        return out

    def flush(self) -> list[tuple[str, bool]]:
        out: list[tuple[str, bool]] = []
        if self.mode == "call":
            self.calls.append(self._call + self.buf)
        elif self.buf:
            out.append((self.buf, self.mode == "think"))
        self.buf = ""
        return out

    def _emit(self, out: list[tuple[str, bool]], text: str) -> None:
        if not text:
            return
        if self.mode == "call":
            self._call += text
        else:
            out.append((text, self.mode == "think"))

    def _step(self, out: list[tuple[str, bool]]) -> bool:
        if self.mode == "text":
            opens = [(self.buf.find(t), t) for t in (THINK_OPEN, CALL_OPEN)]
            hits = sorted((i, t) for i, t in opens if i >= 0)
            if hits:
                i, tag = hits[0]
                self._emit(out, self.buf[:i])
                self.buf = self.buf[i + len(tag) :]
                self.mode = "think" if tag == THINK_OPEN else "call"
                self._call = ""
                return True
            tags: tuple[str, ...] = (THINK_OPEN, CALL_OPEN)
        else:
            close = THINK_CLOSE if self.mode == "think" else CALL_CLOSE
            i = self.buf.find(close)
            if i >= 0:
                self._emit(out, self.buf[:i])
                if self.mode == "call":
                    self.calls.append(self._call)
                self.buf = self.buf[i + len(close) :]
                self.mode = "text"
                return True
            tags = (close,)
        keep = _hold(self.buf, tags)
        self._emit(out, self.buf[: len(self.buf) - keep])
        self.buf = self.buf[len(self.buf) - keep :]
        return False


def parse_arguments(raw: str) -> tuple[dict[str, Any], str | None]:
    """Parse tool arguments, tolerating empty input and truncated JSON."""
    if not raw.strip():
        return {}, None
    for suffix in _REPAIRS:
        try:
            value = json.loads(raw + suffix)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value, None
        break
    return {}, "arguments are not a valid JSON object"


def parse_tag_call(body: str, types: dict[str, str] | None = None) -> ParsedToolCall:
    """Parse one <tool_call> body: JSON object or Qwen XML <function=..>.

    `types` maps parameter name to its schema type so string parameters keep
    their text verbatim (a file containing `42` must stay a string).
    """
    body = body.strip()
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return ParsedToolCall(
                new_call_id(), "", {}, body, "malformed tool call JSON"
            )
        args = data.get("arguments", data.get("parameters", {}))
        if isinstance(args, str):
            args, err = parse_arguments(args)
        else:
            err = None if isinstance(args, dict) else "arguments must be an object"
            args = args if isinstance(args, dict) else {}
        return ParsedToolCall(
            new_call_id(), str(data.get("name", "")), args, json.dumps(args), err
        )
    m = _FUNC_RE.search(body)
    if m is None:
        return ParsedToolCall(new_call_id(), "", {}, body, "unrecognised tool call")
    hints = types or {}
    args = {k: _coerce(v, hints.get(k)) for k, v in _PARAM_RE.findall(m.group(2))}
    return ParsedToolCall(new_call_id(), m.group(1), args, json.dumps(args))


def _coerce(value: str, schema_type: str | None) -> Any:
    """XML parameters are strings; decode JSON for non-string schema types only."""
    if schema_type in (None, "string"):
        return value
    try:
        return json.loads(value.strip())
    except json.JSONDecodeError:
        return value
