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
