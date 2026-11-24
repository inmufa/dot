"""WebFetch: fetch a public URL through the SSRF guard and return markdown."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.tools.web.errors import one_line, web_error
from backend.cognition.services.tools.web.fetch_http import SafeFetcher
from backend.cognition.services.tools.web.page_text import TtlCache, to_text
from backend.core.exceptions import DomainException

OUTPUT_CHARS = 22_000  # page text cap plus header lines


def make_fetch_tool(fetcher: SafeFetcher, cache: TtlCache | None = None) -> Tool:
    cache = cache or TtlCache()

    async def run(_ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        url = str(a["url"]).strip()
        text = cache.get(url)
        if text is None:
            try:
                page = await fetcher.get(url)
            except DomainException as exc:
                return web_error("WebFetch", exc)
            body = await to_text(page)
            moved = (
                f"\nRedirected to: {one_line(page.url, 500)}" if page.redirected else ""
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
            "Fetch a public http(s) URL and return its content as markdown "
            "(first 20000 chars). Private, local and metadata addresses are "
            "blocked. 'prompt' says what you look for; read the result yourself. "
            "Results are cached for 15 minutes."
        ),
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string"}, "prompt": {"type": "string"}},
            "required": ["url"],
        },
    )
    return Tool(definition, run, max_chars=OUTPUT_CHARS)
