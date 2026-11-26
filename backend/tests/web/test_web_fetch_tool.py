import httpx
from backend.cognition.services.tools.web.fetch import make_fetch_tool
from backend.cognition.services.tools.web.page_text import TtlCache
from web_helpers import ctx, fetcher, html_page


def tool_with(handler, cache: TtlCache | None = None):
    return make_fetch_tool(fetcher(handler), cache)


async def test_definition_is_core_read_only():
    d = tool_with(lambda _r: html_page("x")).definition
    assert (d.name, d.deferred, d.mutating) == ("WebFetch", False, False)


async def test_fetch_returns_tainted_markdown():
    t = tool_with(
        lambda _r: html_page(
            "<article><h1>Hi</h1><p>" + "word " * 60 + "</p></article>", "Page"
        )
    )
    r = await t.run(
        ctx(), {"url": "http://example.com/a", "prompt": "find the greeting"}
    )
    assert r.tainted
    assert not r.is_error
    assert "URL: http://example.com/a" in r.output
    assert "Looking for: find the greeting" in r.output
    assert "Title: " in r.output


async def test_second_fetch_is_served_from_cache():
    hits = []

    def handler(req: httpx.Request) -> httpx.Response:
        hits.append(req)
        return html_page("<p>" + "cached text " * 30 + "</p>")

    t = tool_with(handler)
    a = await t.run(ctx(), {"url": "http://example.com/c"})
    b = await t.run(ctx(), {"url": "http://example.com/c"})
    await t.run(ctx(), {"url": "http://example.com/other"})
    assert len(hits) == 2
    assert a.output == b.output
    assert b.tainted  # cached results stay tainted


async def test_errors_are_results_not_exceptions():
    t = tool_with(lambda _r: html_page("x"))
    r = await t.run(ctx(), {"url": "http://127.0.0.1:8080/admin"})
    assert r.is_error
    assert "error 4012" in r.output
    assert "loopback" in r.output
    assert not r.tainted
    r = await t.run(ctx(), {"url": "http://good@127.0.0.1/"})
    assert "error 4012" in r.output


async def test_binary_is_rejected_with_a_message():
    t = tool_with(
        lambda _r: httpx.Response(
            200, content=b"%PDF", headers={"content-type": "application/pdf"}
        )
    )
    r = await t.run(ctx(), {"url": "http://example.com/x.pdf"})
    assert r.is_error
    assert "error 4014" in r.output


async def test_redirect_is_reported():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "http://example.com/new"})
        return html_page("<p>" + "moved here " * 30 + "</p>")

    r = await tool_with(handler).run(ctx(), {"url": "http://example.com/old"})
    assert "Redirected to: http://example.com/new" in r.output


class FakeBrowser:
    """Stands in for BrowserClient.post; `pages` are successive /extract results."""

    def __init__(self, *pages: str) -> None:
        self.pages = list(pages)
        self.calls: list[tuple[str, str]] = []

    async def post(self, session_id: str, path: str, _payload: dict) -> dict:
        self.calls.append((session_id, path))
        if path == "/extract":
            return {"markdown": self.pages.pop(0), "title": "Hotels"}
        return {}


WALL = "JavaScript is disabled. Verify that you're not a robot. Enable JavaScript and reload."


async def test_blocked_status_falls_back_to_the_browser(monkeypatch):
    b = FakeBrowser("# Hotels\nreal list")
    t = make_fetch_tool(fetcher(lambda _r: httpx.Response(429)), browser=b)
    r = await t.run(ctx(), {"url": "http://example.com/h"})
    assert not r.is_error
    assert r.tainted
    assert "real list" in r.output
    assert "read with a browser" in r.output
    assert b.calls[0] == ("webfetch", "/nav")  # hidden session, not the chat's tab


async def test_bot_check_page_falls_back_to_the_browser(monkeypatch):
    monkeypatch.setattr(
        "backend.cognition.services.tools.web.fetch.CHALLENGE_WAIT_S", 0
    )
    b = FakeBrowser(WALL, "# Hotels\ncleared")
    t = make_fetch_tool(fetcher(lambda _r: html_page(f"<p>{WALL}</p>")), browser=b)
    r = await t.run(ctx(), {"url": "http://example.com/m"})
    assert "cleared" in r.output


async def test_wall_everywhere_says_to_use_another_source(monkeypatch):
    monkeypatch.setattr(
        "backend.cognition.services.tools.web.fetch.CHALLENGE_WAIT_S", 0
    )
    t = make_fetch_tool(
        fetcher(lambda _r: httpx.Response(503)), browser=FakeBrowser(WALL, WALL)
    )
    r = await t.run(ctx(), {"url": "http://example.com/x"})
    assert r.is_error
    assert "error 4013" in r.output
    assert "another source" in r.output


async def test_plain_errors_skip_the_browser():
    b = FakeBrowser()
    t = make_fetch_tool(fetcher(lambda _r: httpx.Response(404)), browser=b)
    r = await t.run(ctx(), {"url": "http://example.com/gone"})
    assert r.is_error
    assert not b.calls
