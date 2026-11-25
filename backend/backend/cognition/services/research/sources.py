"""Pull citable sources out of web tool results (untrusted text, strictly capped)."""

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from dot_contracts.events import SourceItem

from backend.core.text import strip_control_tags

MAX_SOURCES = 40
TITLE_CHARS = 160
URL_CHARS = 500
SNIPPET_CHARS = 240
_CTRL = re.compile(r"[\x00-\x1f\x7f\u200b-\u200f\u2028-\u202e]")
_ITEM = re.compile(r"^\s*\d+\. (?P<title>.*)\n\s+(?P<url>\S+)\n(?P<rest>[^\n]*)", re.M)
_FETCH_URL = re.compile(r"^(?:Redirected to|URL): (\S+)", re.M)
_PAGE = re.compile(r"^Page: (\S+)\nTitle: (.*)$", re.M)
_HEADING = re.compile(r"^#{1,3}\s+(.+)$", re.M)
_ENGINES = re.compile(r"\s*\[[^\]]{1,80}\]$")
_WEB_TOOLS = frozenset({"WebSearch", "WebFetch"})


def clean(text: str, limit: int) -> str:
    """One line, no control characters or control tags, capped."""
    text = " ".join(_CTRL.sub(" ", strip_control_tags(text)).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def clean_url(raw: str) -> str | None:
    """http(s) URL without credentials or fragment, or None."""
    raw = _CTRL.sub("", raw.strip())
    if len(raw) > URL_CHARS or any(c in raw for c in "<>\"' \\"):
        return None
    try:
        parts = urlsplit(raw)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host or "@" in parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def is_web_tool(name: str) -> bool:
    return name in _WEB_TOOLS or name.startswith("Browser")


def _search(output: str) -> list[tuple[str, str, str]]:
    out = []
    for m in _ITEM.finditer(output):
        snippet = _ENGINES.sub("", m["rest"].strip())
        out.append((m["url"], m["title"], snippet))
    return out


def _fetch(output: str, args: dict[str, Any]) -> list[tuple[str, str, str]]:
    urls = _FETCH_URL.findall(output[:1200]) or [str(args.get("url", ""))]
    body = output.split("\n---\n", 1)[-1]
    heading = _HEADING.search(body)
    title = heading[1] if heading else ""
    snippet = body.lstrip("# ").strip()[: SNIPPET_CHARS * 2]
    return [(urls[-1], title, snippet)]


def _page(output: str) -> list[tuple[str, str, str]]:
    m = _PAGE.search(output[:1500])
    return [(m[1], m[2], "")] if m else []


def extract(name: str, args: dict[str, Any], output: str) -> list[SourceItem]:
    """Candidate sources of one tool result; `n` is 0 until the tracker numbers them."""
    if name == "WebSearch":
        raw = _search(output)
    elif name == "WebFetch":
        raw = _fetch(output, args)
    elif name.startswith("Browser"):
        raw = _page(output)
    else:
        raw = []
    items = []
    for url, title, snippet in raw:
        if (clean_url_ := clean_url(url)) is None:
            continue
        host = urlsplit(clean_url_).hostname or clean_url_
        items.append(
            SourceItem(
                n=0,
                title=clean(title, TITLE_CHARS) or host,
                url=clean_url_,
                snippet=clean(snippet, SNIPPET_CHARS) or None,
            )
        )
    return items


def add_sources(
    store: list[dict[str, Any]], found: list[SourceItem]
) -> list[SourceItem]:
    """Number and dedupe into the turn list (dicts); returns this call's items."""
    out: list[SourceItem] = []
    by_url = {d["url"]: d for d in store}
    for item in found:
        known = by_url.get(item.url)
        if known is None:
            if len(store) >= MAX_SOURCES:
                continue
            known = {**item.model_dump(), "n": len(store) + 1}
            store.append(known)
            by_url[item.url] = known
        elif item.snippet and not known.get("snippet"):
            known["snippet"] = item.snippet
        out.append(SourceItem(**known))
    return out
