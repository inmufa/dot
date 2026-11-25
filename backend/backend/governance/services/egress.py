"""Outbound-capable tools: a URL or query is a data channel, so unusual ones need a human."""

import math
import re
from collections import Counter
from typing import Any
from urllib.parse import urlsplit

from backend.governance.services.taint import TaintStore

URL_TOOLS = {"WebFetch": "url", "BrowserNavigate": "url"}
QUERY_TOOLS = {"WebSearch": "query"}
OUTBOUND = frozenset(URL_TOOLS) | frozenset(QUERY_TOOLS)
_MAX_QUERY = (
    200  # chars of URL query string or search text before it looks like a payload
)
_TOKEN = re.compile(r"[A-Za-z0-9+/_=%-]{24,}")
_ENTROPY = 3.5


def _entropy(text: str) -> float:
    n = len(text)
    return -sum(c / n * math.log2(c / n) for c in Counter(text).values())


def looks_encoded(text: str) -> str | None:
    """A long high-entropy token (base64, hex, key) hiding in a URL or query."""
    for tok in _TOKEN.findall(text):
        if len(tok) >= 32 and _entropy(tok) >= _ENTROPY:  # noqa: PLR2004
            return f"long encoded value ({tok[:12]}...)"
    return None


def _url_reason(taint: TaintStore, session: str, url: str) -> str | None:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "malformed URL"
    if parts.username or parts.password:
        return "URL carries credentials"
    if len(parts.query) > _MAX_QUERY:
        return f"URL query string is {len(parts.query)} chars"
    if hit := looks_encoded(parts.path + "?" + parts.query):
        return f"URL carries a {hit}"
    if taint.consumed(session) and not taint.url_known(session, url):
        return "URL was composed by the model after untrusted content entered the chat"
    return None


def egress_reason(
    taint: TaintStore, session: str, name: str, args: dict[str, Any]
) -> str | None:
    """Why this outbound call needs approval, or None. Bypass mode skips this."""
    if name in URL_TOOLS:
        url = str(args.get(URL_TOOLS[name]) or "")
        return _url_reason(taint, session, url) if url else None
    if name in QUERY_TOOLS:
        query = str(args.get(QUERY_TOOLS[name]) or "")
        if len(query) > _MAX_QUERY:
            return f"search text is {len(query)} chars"
        if hit := looks_encoded(query):
            return f"search text carries a {hit}"
        if taint.consumed(session) and (rep := taint.overlap(session, {"q": query})):
            return f"search text {rep}"
    return None
