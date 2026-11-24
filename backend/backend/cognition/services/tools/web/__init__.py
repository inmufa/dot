"""Web tools: WebSearch and WebFetch (core), Browser* (deferred)."""

from collections.abc import Awaitable, Callable

import httpx

from backend.cognition.services.tools.registry import Tool, ToolRegistry
from backend.cognition.services.tools.web.browser import make_browser_tools
from backend.cognition.services.tools.web.browser_client import BrowserClient
from backend.cognition.services.tools.web.fetch import make_fetch_tool
from backend.cognition.services.tools.web.fetch_http import SafeFetcher
from backend.cognition.services.tools.web.search import SearxngClient, make_search_tool
from backend.core.ssrf import Resolver, system_resolver
from backend.settings import Settings

__all__ = ["add_web_tools", "make_web_tools"]


Closer = Callable[[], Awaitable[None]]


def build_web_tools(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    resolver: Resolver = system_resolver,
) -> tuple[list[Tool], list[Closer]]:
    """Tools in prefix order (WebSearch, WebFetch, deferred browser set) + closers.

    `transport` replaces the network for all three clients (tests).
    """
    http = (
        httpx.AsyncClient(transport=transport, trust_env=False) if transport else None
    )
    searx = SearxngClient(settings.searxng_url, http)
    fetcher = SafeFetcher(
        resolver=resolver,
        allow_loopback=settings.web_unsafe_allow_loopback,
        transport=transport,
    )
    browser = BrowserClient(settings.browser_url, settings.browser_token, http)
    tools = [
        make_search_tool(searx),
        make_fetch_tool(fetcher),
        *make_browser_tools(browser),
    ]
    return tools, [searx.aclose, fetcher.aclose, browser.aclose]


def make_web_tools(settings: Settings, **kw) -> list[Tool]:
    return build_web_tools(settings, **kw)[0]


def add_web_tools(registry: ToolRegistry, settings: Settings) -> list[Closer]:
    tools, closers = build_web_tools(settings)
    for tool in tools:
        registry.add(tool)
    return closers
