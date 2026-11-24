"""Neutralise markup that could impersonate the system or the model."""

import re

_TAGS = re.compile(
    r"<(/?)(system-reminder|tool_call|think|function=|untrusted-summary|"
    r"conversation-summary|dot-md|memory-index|file\b)",
    re.IGNORECASE,
)
_CHATML = re.compile(r"<\|[^|>\n]{1,40}\|>")
_BOUNDARY = "CACHE_BOUNDARY"


def strip_control_tags(text: str) -> str:
    """Break control tags (zero-width space after `<`), drop chat-template tokens."""
    text = _CHATML.sub("", text)
    text = text.replace(_BOUNDARY, "CACHE-BOUNDARY")
    return _TAGS.sub(lambda m: f"<\u200b{m[1]}{m[2]}", text)
