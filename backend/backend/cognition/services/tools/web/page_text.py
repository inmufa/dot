"""Fetched bytes to readable markdown, plus a small in-memory TTL cache."""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable

import trafilatura

from backend.cognition.services.tools.web.errors import one_line
from backend.cognition.services.tools.web.fetch_http import Fetched
from backend.core.text import strip_control_tags

MAX_CHARS = 20_000
CACHE_TTL_S = 900.0
CACHE_ENTRIES = 64
_HTML = ("text/html", "application/xhtml+xml")


def _decode(f: Fetched) -> str:
    try:
        return f.body.decode(f.charset or "utf-8", errors="replace")
    except LookupError:
        return f.body.decode("utf-8", errors="replace")


def _html_to_markdown(html: str) -> tuple[str, str]:
    """(title, markdown); falls back to plain text when extraction finds nothing."""
    text = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        favor_recall=True,
    )
    meta = trafilatura.extract_metadata(html)
    title = (meta.title or "") if meta else ""
    return title, text or trafilatura.html2txt(html) or ""


async def to_text(f: Fetched) -> str:
    """Page text with title header, control tags neutralised, capped at MAX_CHARS."""
    raw = _decode(f)
    title = ""
    if f.content_type in _HTML:
        title, raw = await asyncio.to_thread(_html_to_markdown, raw)
    body = strip_control_tags(raw).strip() or "(the page has no readable text)"
    note = ""
    if len(body) > MAX_CHARS:
        body, note = (
            body[:MAX_CHARS],
            f"\n[truncated: showing the first {MAX_CHARS} chars]",
        )
    elif f.truncated:
        note = "\n[truncated: the page was larger than the download cap]"
    head = f"Title: {one_line(title, 200)}\n" if title else ""
    return f"{head}{body}{note}"


class TtlCache:
    def __init__(
        self,
        ttl_s: float = CACHE_TTL_S,
        size: int = CACHE_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl, self._size, self._clock = ttl_s, size, clock
        self._items: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get(self, key: str) -> str | None:
        hit = self._items.get(key)
        if hit is None:
            return None
        if self._clock() - hit[0] > self._ttl:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return hit[1]

    def put(self, key: str, value: str) -> None:
        self._items[key] = (self._clock(), value)
        self._items.move_to_end(key)
        while len(self._items) > self._size:
            self._items.popitem(last=False)
