"""WebFetch: fetch a public URL through the SSRF guard and return markdown."""

import asyncio
import re
from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.tools.web.browser_client import BrowserClient
from backend.cognition.services.tools.web.errors import one_line, web_error
from backend.cognition.services.tools.web.fetch_http import FETCH_FAILED, SafeFetcher
from backend.cognition.services.tools.web.page_text import TtlCache, to_text
from backend.core.exceptions import DomainException
from backend.core.text import strip_control_tags

OUTPUT_CHARS = 22_000  # page text cap plus header lines
BROWSER_CHARS = 20_000
# one hidden worker context for all fallbacks, apart from the visible agent browser
BROWSER_SESSION = "webfetch"
CHALLENGE_WAIT_S = 5.0
_WALL_STATUS = re.compile(r"HTTP (401|403|429|503)\b")
# bot-check interstitials served with a 200
_CHALLENGE = re.compile(
    r"verify (that )?you('| a)re (not a robot|human)|enable javascript and"
    r"|javascript is disabled|just a moment\.\.\.|checking your browser"
    r"|attention required|access denied|are you a robot|captcha",
    re.IGNORECASE,
)


def _walled(exc: DomainException) -> bool:
    return exc.code == FETCH_FAILED and bool(
        _WALL_STATUS.search(str(exc.ctx.get("detail", "")))
    )


def _challenge(text: str) -> bool:
    # real articles can mention captchas; a wall is short
    return len(text) < 3000 and bool(_CHALLENGE.search(text))  # noqa: PLR2004


async def _via_browser(b: BrowserClient, url: str) -> str | None:
    """Page text from real Chromium, or None when that is blocked too."""
    try:
        await b.post(BROWSER_SESSION, "/nav", {"url": url})
        d = await b.post(BROWSER_SESSION, "/extract", {})
        md = str(d.get("markdown", ""))
        if _challenge(md):  # JS challenges usually clear themselves in a few seconds
            await asyncio.sleep(CHALLENGE_WAIT_S)
            d = await b.post(BROWSER_SESSION, "/extract", {})
            md = str(d.get("markdown", ""))
    except DomainException:
        return None
    if not md.strip() or _challenge(md):
        return None
    title = one_line(str(d.get("title", "")), 200)
    return f"Title: {title}\n{strip_control_tags(md)[:BROWSER_CHARS]}"


def make_fetch_tool(
    fetcher: SafeFetcher,
    cache: TtlCache | None = None,
    browser: BrowserClient | None = None,
) -> Tool:
    cache = cache or TtlCache()

    async def run(_ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        url = str(a["url"]).strip()
        text = cache.get(url)
        if text is None:
            body: str | None = None
            moved, failure = "", None
            try:
                page = await fetcher.get(url)
                body = await to_text(page)
                if page.redirected:
                    moved = f"\nRedirected to: {one_line(page.url, 500)}"
            except DomainException as exc:
                if not (browser and _walled(exc)):
                    return web_error("WebFetch", exc)
                failure = exc
            if browser and (body is None or _challenge(body)):
                via = await _via_browser(browser, url)
                if via is not None:
                    body, moved = (
                        via,
                        "\n(read with a browser: the site blocks plain fetches)",
                    )
                elif failure is not None:
                    out = web_error("WebFetch", failure)
                    out.output += (
                        "\nThe site blocks automated readers, a browser too. "
                        "Use another source."
                    )
                    return out
                else:
                    return ToolResult(
                        call_id="",
                        output=(
                            "WebFetch: the site served a bot check instead of the "
                            "page, a browser too. Use another source."
                        ),
                        is_error=True,
                    )
            text = f"URL: {one_line(url, 500)}{moved}\n---\n{body}"
            cache.put(url, text)
        prompt = a.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            text = f"Looking for: {one_line(prompt, 200)}\n{text}"
        return ToolResult(call_id="", output=text, tainted=True)

    definition = ToolDefinition(
        name="WebFetch",
        mutating=False,
        description=(
            "Read a public http(s) page as markdown (first 20000 chars): articles, "
            "docs, search results, raw files, JSON APIs. Default for reading any "
            "page; falls back to a real browser by itself when a site blocks "
            "plain fetches. If it still fails, use another source, do not retry "
            "the same site. 'prompt' says what you look for; read the result "
            "yourself. Cached for 15 minutes."
        ),
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}, "prompt": {"type": "string"}},
            "required": ["url"],
        },
    )
    return Tool(definition, run, max_chars=OUTPUT_CHARS)
