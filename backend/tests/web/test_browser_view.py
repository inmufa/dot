import httpx
from backend.cognition.services.tools.web.browser import make_browser_tools
from fastapi import FastAPI
from helpers import new_session
from httpx import AsyncClient
from web_helpers import ctx

JPEG = b"\xff\xd8\xff\xe0fakejpeg"
STATE = {
    "open": True,
    "tabs": [{"tab": "t1", "url": "https://example.com/", "title": "Ex"}],
    "active": "t1",
    "url": "https://example.com/",
    "title": "Ex",
    "loading": False,
    "viewport": {"width": 1280, "height": 800},
    "blocked": None,
}


class Fake:
    """Stands in for the browser worker."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.down = False
        self.blocked = False
        self.fail: tuple[int, str] | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        if self.down:
            msg = "refused"
            raise httpx.ConnectError(msg)
        path = req.url.path
        if self.blocked and path in ("/nav", "/tabs/new"):
            return httpx.Response(
                403, json={"error": "ssrf_blocked", "detail": "private address"}
            )
        if self.fail and path not in ("/view/state", "/view/frame"):
            return httpx.Response(
                self.fail[0], json={"error": self.fail[1], "detail": "net::ERR"}
            )
        if path == "/view/frame":
            return httpx.Response(
                200, content=JPEG, headers={"content-type": "image/jpeg"}
            )
        if path == "/view/state":
            return httpx.Response(200, json=STATE)
        return httpx.Response(200, json={**STATE, "status": 200})


async def setup(app: FastAPI, authed: AsyncClient) -> tuple[Fake, str]:
    fake = Fake()
    browser = app.state.browser_view._b
    browser._client = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    return fake, await new_session(authed, "bypass")


async def test_state_and_frame(app: FastAPI, authed: AsyncClient) -> None:
    fake, sid = await setup(app, authed)
    st = (await authed.get(f"/v1/sessions/{sid}/browser/state")).json()
    assert st["open"] is True
    assert st["agent_acting"] is False
    assert st["agent_seq"] == 0
    r = await authed.post(f"/v1/sessions/{sid}/browser/frame", json={})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == JPEG
    # the worker session id is the Dot session id, shared with the agent tools
    assert {c.headers["x-session-id"] for c in fake.calls} == {sid}


async def test_requires_auth_and_known_session(
    app: FastAPI, authed: AsyncClient, client: AsyncClient
) -> None:
    _, sid = await setup(app, authed)
    anon = AsyncClient(transport=client._transport, base_url="http://test")
    assert (await anon.get(f"/v1/sessions/{sid}/browser/state")).status_code == 401
    r = await authed.get("/v1/sessions/Snope/browser/state")
    assert r.status_code == 404


async def test_actions_forward_and_are_audited(
    app: FastAPI, authed: AsyncClient
) -> None:
    fake, sid = await setup(app, authed)
    base = f"/v1/sessions/{sid}/browser"
    await authed.post(f"{base}/navigate", json={"url": "https://example.com/x"})
    await authed.post(f"{base}/click", json={"x": 10.5, "y": 20})
    await authed.post(f"{base}/type", json={"text": "hunter2-secret"})
    await authed.post(f"{base}/press", json={"key": "Enter"})
    await authed.post(f"{base}/scroll", json={"dy": 300, "x": 5, "y": 5})
    for p in ("back", "forward", "reload"):
        assert (await authed.post(f"{base}/{p}", json={})).status_code == 200
    await authed.post(f"{base}/tabs/new", json={})
    await authed.post(f"{base}/tabs/switch", json={"tab": "t1"})
    await authed.post(f"{base}/tabs/close", json={"tab": "t1"})
    paths = [c.url.path for c in fake.calls if c.method == "POST"]
    for want in (
        "/nav",
        "/view/click",
        "/view/type",
        "/press",
        "/view/wheel",
        "/view/back",
        "/view/forward",
        "/view/reload",
        "/tabs/new",
        "/tabs/switch",
        "/close",
    ):
        assert want in paths
    log = (await authed.get("/v1/audit", params={"session": sid})).json()
    rows = log["items"] if isinstance(log, dict) else log
    tools = {r["tool"] for r in rows}
    assert {"BrowserView.navigate", "BrowserView.click", "BrowserView.type"} <= tools
    assert "BrowserView.scroll" not in tools
    assert all(r["source"] == "user" for r in rows)
    assert "hunter2" not in str(rows)


async def test_blocked_url_is_4018(app: FastAPI, authed: AsyncClient) -> None:
    fake, sid = await setup(app, authed)
    fake.blocked = True
    r = await authed.post(
        f"/v1/sessions/{sid}/browser/navigate", json={"url": "http://10.0.0.1/"}
    )
    assert r.status_code == 403
    assert "4018" in r.text


async def test_worker_down_is_4015(app: FastAPI, authed: AsyncClient) -> None:
    fake, sid = await setup(app, authed)
    fake.down = True
    r = await authed.get(f"/v1/sessions/{sid}/browser/state")
    assert r.status_code == 502
    assert "4015" in r.text


async def test_input_rejected_while_agent_acts(
    app: FastAPI, authed: AsyncClient
) -> None:
    _fake, sid = await setup(app, authed)
    browser = app.state.browser_view._b
    seen: dict = {}
    base = f"/v1/sessions/{sid}/browser"

    async def agent_call() -> None:
        # while the agent call is in flight the busy flag is set
        browser.acting[sid] = 1
        seen["state"] = (await authed.get(f"{base}/state")).json()
        seen["click"] = await authed.post(f"{base}/click", json={"x": 1, "y": 1})
        seen["frame"] = await authed.post(f"{base}/frame", json={})
        del browser.acting[sid]

    await agent_call()
    assert seen["state"]["agent_acting"] is True
    assert seen["click"].status_code == 409
    assert "4017" in seen["click"].text
    assert seen["frame"].status_code == 200  # viewing is always allowed


async def test_agent_tools_bump_the_counter(app: FastAPI, authed: AsyncClient) -> None:
    _fake, sid = await setup(app, authed)
    browser = app.state.browser_view._b
    nav = next(
        t for t in make_browser_tools(browser) if t.definition.name == "BrowserNavigate"
    )
    await nav.run(ctx(sid), {"url": "https://example.com/"})
    st = (await authed.get(f"/v1/sessions/{sid}/browser/state")).json()
    # navigate now makes two calls under the hood (/nav then /snapshot folded in)
    assert st["agent_seq"] == 2
    assert st["agent_acting"] is False
    assert browser.acting == {}


async def test_rate_limit(app: FastAPI, authed: AsyncClient) -> None:
    _, sid = await setup(app, authed)
    app.state.settings.browser_view_burst = 3
    app.state.browser_view._buckets.clear()
    codes = [
        (await authed.get(f"/v1/sessions/{sid}/browser/state")).status_code
        for _ in range(6)
    ]
    assert 429 in codes


async def test_viewport_is_forwarded_quietly(app: FastAPI, authed: AsyncClient) -> None:
    fake, sid = await setup(app, authed)
    base = f"/v1/sessions/{sid}/browser"
    r = await authed.post(f"{base}/viewport", json={"width": 536, "height": 720})
    assert r.status_code == 200
    assert r.json()["viewport"] == STATE["viewport"]
    call = next(c for c in fake.calls if c.url.path == "/view/viewport")
    assert call.read() == b'{"width":536,"height":720}'
    bad = await authed.post(f"{base}/viewport", json={"width": 0, "height": 720})
    assert bad.status_code == 422
    log = (await authed.get("/v1/audit", params={"session": sid})).json()
    rows = log["items"] if isinstance(log, dict) else log
    assert not any(r["tool"] == "BrowserView.viewport" for r in rows)
    app.state.browser_view._b.acting[sid] = 1
    busy = await authed.post(f"{base}/viewport", json={"width": 600, "height": 700})
    assert busy.status_code == 409
    del app.state.browser_view._b.acting[sid]


async def test_owner_navigation_returns_at_commit(
    app: FastAPI, authed: AsyncClient
) -> None:
    fake, sid = await setup(app, authed)
    base = f"/v1/sessions/{sid}/browser"
    await authed.post(f"{base}/navigate", json={"url": "https://example.com/"})
    await authed.post(f"{base}/tabs/new", json={"url": "https://example.com/"})
    await authed.post(f"{base}/tabs/new", json={})
    sent = [c.read() for c in fake.calls if c.url.path in ("/nav", "/tabs/new")]
    assert b'"wait_until":"commit"' in sent[0]
    assert b'"wait_until":"commit"' in sent[1]
    assert sent[2] == b"{}"


async def test_page_load_failure_is_4019(app: FastAPI, authed: AsyncClient) -> None:
    fake, sid = await setup(app, authed)
    base = f"/v1/sessions/{sid}/browser"
    fake.fail = (504, "timeout")
    r = await authed.post(f"{base}/navigate", json={"url": "https://slow.example/"})
    assert r.status_code == 502
    assert "4019" in r.text
    fake.fail = (502, "action_failed")
    r = await authed.post(f"{base}/click", json={"x": 1, "y": 1})
    assert "4016" in r.text  # only page loads map to 4019
