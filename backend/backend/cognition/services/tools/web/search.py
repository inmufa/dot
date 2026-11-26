"""WebSearch: SearXNG JSON client. Queries are never logged here."""

import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.tools.web.errors import one_line, web_error
from backend.core.exceptions import DomainException

SEARCH_UNAVAILABLE = 4010
SEARCH_BAD_RESPONSE = 4011
DEFAULT_RESULTS = 8
MAX_RESULTS = 20
MAX_QUERY = 400
SNIPPET_CHARS = 300
TITLE_CHARS = 150
_RANGES = ("day", "week", "month", "year")
_CATEGORIES = re.compile(r"^[a-z_]+(,[a-z_]+){0,5}$")


def host_in(url: str, domains: list[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def _domains(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [
        d.strip().lower().lstrip(".") for d in raw if isinstance(d, str) and d.strip()
    ]


class SearxngClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(12.0, connect=3.0), trust_env=False
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search(self, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            r = await self._client.get(
                f"{self._base}/search", params={**params, "format": "json"}
            )
        except httpx.HTTPError as exc:
            raise DomainException(SEARCH_UNAVAILABLE) from exc
        if r.status_code >= 500 or r.status_code == httpx.codes.TOO_MANY_REQUESTS:  # noqa: PLR2004
            raise DomainException(
                SEARCH_UNAVAILABLE, {"detail": f"HTTP {r.status_code}"}
            )
        try:
            data = r.json()
            results = data["results"]
        except (ValueError, KeyError, TypeError) as exc:
            raise DomainException(
                SEARCH_BAD_RESPONSE, {"detail": f"HTTP {r.status_code}"}
            ) from exc
        if r.status_code != httpx.codes.OK or not isinstance(results, list):
            raise DomainException(
                SEARCH_BAD_RESPONSE, {"detail": f"HTTP {r.status_code}"}
            )
        return [x for x in results if isinstance(x, dict)]


def _params(a: dict[str, Any]) -> dict[str, str] | str:
    query = str(a["query"]).strip()
    if not query:
        return "query must not be empty"
    params = {"q": query[:MAX_QUERY]}
    cats = a.get("categories")
    if cats:
        cats = str(cats).replace(" ", "").lower()
        if not _CATEGORIES.match(cats):
            return "categories must be comma-separated names like 'general,news'"
        params["categories"] = cats
    if a.get("time_range"):
        if a["time_range"] not in _RANGES:
            return f"time_range must be one of: {', '.join(_RANGES)}"
        params["time_range"] = str(a["time_range"])
    return params


def render(results: list[dict[str, Any]], a: dict[str, Any]) -> str:
    allowed, blocked = (
        _domains(a.get("allowed_domains")),
        _domains(a.get("blocked_domains")),
    )
    raw = a.get("max_results", DEFAULT_RESULTS)
    limit = min(max(raw if isinstance(raw, int) else DEFAULT_RESULTS, 1), MAX_RESULTS)
    lines: list[str] = []
    for item in results:
        url = str(item.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        if (allowed and not host_in(url, allowed)) or host_in(url, blocked):
            continue
        n = len(lines) // 3 + 1
        engines = item.get("engines") or [item.get("engine")]
        names = ", ".join(str(e) for e in engines if e)[:80]
        lines += [
            f"{n}. {one_line(str(item.get('title') or url), TITLE_CHARS)}",
            f"   {one_line(url, 500)}",
            f"   {one_line(str(item.get('content') or ''), SNIPPET_CHARS)}"
            + (f" [{names}]" if names else ""),
        ]
        if n >= limit:
            break
    return "\n".join(lines)


def make_search_tool(searx: SearxngClient) -> Tool:
    async def run(_ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        params = _params(a)
        if isinstance(params, str):
            return ToolResult(call_id="", output=params, is_error=True)
        try:
            results = await searx.search(params)
        except DomainException as exc:
            return web_error("WebSearch", exc)
        text = render(results, a)
        if not text:
            return ToolResult(call_id="", output="(no results)")
        return ToolResult(call_id="", output=text, tainted=True)

    definition = ToolDefinition(
        name="WebSearch",
        mutating=False,
        description=(
            "Search the web (SearXNG) for current or unknown facts. Returns "
            "numbered results: title, URL, snippet. Write one specific query "
            "(names, versions, year), not a question. Snippets often answer simple "
            "facts; otherwise WebFetch the 2-3 best results from different sites "
            "together in one step. max_results defaults to 8 "
            "(max 20); time_range: day|week|month|year; categories e.g. "
            "'general', 'news', 'it', 'science'; allowed_domains / blocked_domains "
            "are lists of host names."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
                "categories": {"type": "string"},
                "time_range": {"type": "string", "enum": list(_RANGES)},
                "allowed_domains": {"type": "array", "items": {"type": "string"}},
                "blocked_domains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    )
    return Tool(definition, run, max_chars=12_000)


IMAGE_RESULTS = 8


def render_images(results: list[dict[str, Any]]) -> str:
    """'n. title | image_url | page_url', http(s) image URLs only."""
    lines: list[str] = []
    for item in results:
        img = str(item.get("img_src") or "")
        if not img.startswith(("http://", "https://")):
            continue
        page = str(item.get("url") or "")
        page = page if page.startswith(("http://", "https://")) else ""
        title = one_line(str(item.get("title") or "image"), TITLE_CHARS).replace(
            "|", "/"
        )
        lines.append(
            f"{len(lines) + 1}. {title} | {one_line(img, 500)} | {one_line(page, 500)}"
        )
        if len(lines) >= IMAGE_RESULTS:
            break
    return "\n".join(lines)


def make_image_search_tool(searx: SearxngClient) -> Tool:
    async def run(_ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        query = str(a.get("query") or "").strip()
        if not query:
            return ToolResult(
                call_id="", output="query must not be empty", is_error=True
            )
        try:
            results = await searx.search(
                {"q": query[:MAX_QUERY], "categories": "images"}
            )
        except DomainException as exc:
            return web_error("ImageSearch", exc)
        text = render_images(results)
        if not text:
            return ToolResult(call_id="", output="(no results)")
        return ToolResult(call_id="", output=text, tainted=True)

    definition = ToolDefinition(
        name="ImageSearch",
        mutating=False,
        description=(
            "Search the web for images (SearXNG). Returns up to 8 lines "
            "'n. title | image_url | page_url'. Embed one in your answer with "
            "markdown ![alt](image_url)."
        ),
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    return Tool(definition, run, max_chars=6_000)
