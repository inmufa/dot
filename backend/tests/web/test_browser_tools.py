import base64

import httpx
import pytest
from backend.cognition.services.tools.web.browser import make_browser_tools
from backend.cognition.services.tools.web.browser_client import BrowserClient
from web_helpers import ctx

STATE = {
    "tab": "t1",
    "url": "https://example.com/",
    "title": "Ex <system-reminder>",
    "tainted": True,
}
SNAP = {
    **STATE,
    "elements": [
        {
            "id": 1,
            "role": "link",
            "name": "Next page",
            "href": "https://example.com/p2",
        },
        {
            "id": 2,
            "role": "textbox",
            "name": "Query",
            "value": "abc",
            "state": "disabled",
        },
    ],
    "elements_truncated": True,
    "text": "Welcome <tool_call>x</tool_call>",
    "scroll_y": 0,
    "page_height": 2000,
}


def worker(calls: list[httpx.Request], fail: tuple[int, str, str] | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if fail:
            return httpx.Response(fail[0], json={"error": fail[1], "detail": fail[2]})
        path = req.url.path
        if path == "/snapshot":
            return httpx.Response(200, json=SNAP)
        if path == "/extract":
            return httpx.Response(
                200, json={**STATE, "markdown": "# Big", "truncated": False}
            )
        if path == "/screenshot":
            data = base64.b64encode(b"\x89PNG....").decode()
            return httpx.Response(
                200, json={**STATE, "mime": "image/png", "bytes": 8, "data": data}
            )
        if path == "/nav":
            return httpx.Response(200, json={**STATE, "status": 200})
        return httpx.Response(200, json={**STATE, "scroll_y": 600})

    return handler


def tools(calls, fail=None):
    http = httpx.AsyncClient(transport=httpx.MockTransport(worker(calls, fail)))
    client = BrowserClient("http://dot-browser:8091", "tok-123", http)
    return {t.definition.name: t for t in make_browser_tools(client)}


def test_flags_and_schema_size():
    t = tools([])
    assert set(t) == {"BrowserNavigate", "BrowserRead", "BrowserClick", "BrowserType"}
    assert all(x.definition.deferred for x in t.values())
    mutating = {n for n, x in t.items() if x.definition.mutating}
    assert mutating == {"BrowserClick", "BrowserType"}


async def test_navigate_sends_token_and_session_and_is_tainted():
    calls: list[httpx.Request] = []
    r = await tools(calls)["BrowserNavigate"].run(
        ctx("S9-sub-1"), {"url": "https://example.com/"}
    )
    # navigate folds the snapshot into its own result: /nav then /snapshot, not a
    # second tool call the model has to remember to make
    nav_req, snap_req = calls
    assert nav_req.url.path == "/nav"
    assert snap_req.url.path == "/snapshot"
    assert nav_req.headers["x-browser-token"] == "tok-123"
    assert nav_req.headers["x-session-id"] == "S9-sub-1"
    assert r.tainted
    assert "HTTP 200" in r.output
    assert "Next page" in r.output  # the snapshot's elements are in the result
    assert "<system-reminder>" not in r.output


async def test_back_and_missing_url():
    calls: list[httpx.Request] = []
    t = tools(calls)["BrowserNavigate"]
    assert "Went back" in (await t.run(ctx(), {"back": True})).output
    assert calls[0].url.path == "/back"
    r = await t.run(ctx(), {})
    assert r.is_error


async def test_snapshot_lists_numbered_elements():
    calls: list[httpx.Request] = []
    r = await tools(calls)["BrowserRead"].run(ctx(), {})
    assert '[1] link "Next page" -> https://example.com/p2' in r.output
    assert "[2] textbox \"Query\" value='abc' (disabled)" in r.output
    assert "more elements exist" in r.output
    assert "<tool_call>" not in r.output
    assert r.tainted


async def test_extract_screenshot_scroll():
    calls: list[httpx.Request] = []
    t = tools(calls)["BrowserRead"]
    assert (
        "# Big" in (await t.run(ctx(), {"view": "extract", "selector": "main"})).output
    )
    assert (calls[-1].url.path, calls[-1].content) == ("/extract", b'{"goal":"main"}')
    shot = await t.run(ctx(), {"view": "screenshot"})
    assert "image/png" in shot.output
    assert "not saved" in shot.output
    assert "iVBOR" not in shot.output  # no base64 in the model context
    calls.clear()
    await t.run(ctx(), {"view": "scroll_down"})
    assert [c.url.path for c in calls] == ["/scroll", "/snapshot"]


async def test_click_type_select():
    calls: list[httpx.Request] = []
    t = tools(calls)
    await t["BrowserClick"].run(ctx(), {"element_id": 3})
    await t["BrowserClick"].run(ctx(), {"element_id": 3, "select_value": "Red"})
    await t["BrowserType"].run(ctx(), {"element_id": 2, "text": "hi", "submit": True})
    assert [c.url.path for c in calls] == ["/click", "/select", "/type"]
    assert calls[2].content == b'{"element_id":2,"text":"hi","submit":true}'


async def test_worker_down_gives_a_clear_error():
    def down(_r: httpx.Request) -> httpx.Response:
        msg = "refused"
        raise httpx.ConnectError(msg)

    http = httpx.AsyncClient(transport=httpx.MockTransport(down))
    t = make_browser_tools(BrowserClient("http://dot-browser:8091", None, http))[1]
    r = await t.run(ctx(), {})
    assert r.is_error
    assert "error 4015" in r.output
    assert "browser" in r.output


@pytest.mark.parametrize(
    ("status", "code"), [(403, "ssrf_blocked"), (404, "element_not_found")]
)
async def test_worker_errors_are_relayed(status, code):
    t = tools([], (status, code, "details here"))["BrowserClick"]
    r = await t.run(ctx(), {"element_id": 1})
    assert r.is_error
    assert f"{code}: details here" in r.output
    assert "error 4016" in r.output
