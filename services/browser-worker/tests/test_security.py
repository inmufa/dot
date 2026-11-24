import httpx
import pytest
from dot_browser import main
from dot_browser.main import create_app
from dot_browser.settings import Settings

PUBLIC = "93.184.216.34"


async def post(c: httpx.AsyncClient, path: str, **body: object) -> httpx.Response:
    return await c.post(path, json=body)


async def test_default_denies_loopback_fixture(make, server: str) -> None:
    c = await make(loopback=False)
    r = await post(c, "/nav", url=f"{server}/form")
    assert r.status_code == 403
    assert r.json()["error"] == "ssrf_blocked"
    assert "address not allowed" in r.json()["detail"]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/html,<h1>x</h1>",
        "chrome://version",
        "ftp://example.com/x",
        "javascript:alert(1)",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.0.1/",
        "http://[::1]/",
        "http://localhost/",
    ],
)
async def test_blocked_navigations(make, url: str) -> None:
    client = await make(loopback=False)
    r = await post(client, "/nav", url=url)
    assert r.status_code == 403
    assert r.json()["error"] == "ssrf_blocked"


@pytest.mark.parametrize("path", ["/to-private", "/to-lan"])
async def test_redirect_to_private_blocked(
    client: httpx.AsyncClient, server: str, path: str
) -> None:
    r = await post(client, "/nav", url=f"{server}{path}")
    assert r.status_code == 403
    assert r.json()["error"] == "ssrf_blocked"


async def test_public_redirect_followed_and_loop_capped(
    client: httpx.AsyncClient, server: str
) -> None:
    r = await post(client, "/nav", url=f"{server}/to-page2")
    assert r.status_code == 200
    assert r.json()["url"].endswith("/page2")
    loop = await post(client, "/nav", url=f"{server}/loop")
    assert loop.status_code in (403, 502)


async def test_max_redirects_setting(make, server: str) -> None:
    c = await make(max_redirects=0)
    r = await post(c, "/nav", url=f"{server}/to-page2")
    assert r.status_code == 403
    assert "redirect" in r.json()["detail"]


async def test_subrequest_to_private_blocked(
    client: httpx.AsyncClient, server: str
) -> None:
    r = await post(client, "/nav", url=f"{server}/subres")
    assert r.status_code == 200
    assert r.json()["blocked_requests"] >= 1


async def test_dns_rebinding_blocked_by_resolver_check(make) -> None:
    async def res(host: str) -> list[str]:
        return ["10.0.0.9"]

    c = await make(resolver=res, loopback=False)
    r = await post(c, "/nav", url="http://rebind.test/")
    assert r.status_code == 403
    assert "10.0.0.9" in r.json()["detail"]


async def test_dns_rebinding_caught_at_connect(make, server: str) -> None:
    # Early checks see a public answer; the pinned connect sees loopback.
    port = server.rsplit(":", 1)[1]
    calls: list[str] = []

    async def res(host: str) -> list[str]:
        calls.append(host)
        return [PUBLIC] if len(calls) == 1 else ["127.0.0.1"]

    c = await make(resolver=res, loopback=False)
    r = await post(c, "/nav", url=f"http://pub.test:{port}/form")
    assert r.status_code == 403
    assert r.json()["error"] == "ssrf_blocked"
    assert "address not allowed" in r.json()["detail"]
    assert len(calls) >= 2


async def test_deny_list(make, server: str) -> None:
    c = await make(deny_hosts="127.0.0.1")
    assert (await post(c, "/nav", url=f"{server}/form")).status_code == 403


async def test_dialog_dismissed_and_download_ignored(
    client: httpx.AsyncClient, server: str
) -> None:
    r = await post(client, "/nav", url=f"{server}/dialog")
    assert r.status_code == 200
    assert "ok" in (await post(client, "/snapshot")).json()["text"]
    await post(client, "/nav", url=f"{server}/form")
    d = await post(client, "/nav", url=f"{server}/download")
    assert d.status_code in (200, 502)
    assert (await post(client, "/snapshot")).status_code == 200


async def test_popups_limited(make, server: str) -> None:
    c = await make(max_tabs=3)
    await post(c, "/nav", url=f"{server}/popups")
    snap = (await post(c, "/snapshot")).json()
    await post(c, "/click", element_id=snap["elements"][0]["id"])
    tabs = (await c.get("/tabs")).json()
    assert len(tabs["tabs"]) <= 3
    assert (await post(c, "/tabs/new")).status_code in (200, 429)


async def test_tab_cap(make, server: str) -> None:
    c = await make(max_tabs=2)
    await post(c, "/nav", url=f"{server}/form")
    assert (await post(c, "/tabs/new")).status_code == 200
    r = await post(c, "/tabs/new")
    assert r.status_code == 429
    assert r.json()["error"] == "too_many_tabs"


async def test_block_resources_option(make, server: str) -> None:
    c = await make(block_resources=True)
    r = await post(c, "/nav", url=f"{server}/imgpage")
    assert r.status_code == 200


async def test_caps_on_output(make, server: str) -> None:
    c = await make(max_elements=10, max_text_chars=200, max_extract_chars=300)
    await post(c, "/nav", url=f"{server}/many")
    snap = (await post(c, "/snapshot")).json()
    assert len(snap["elements"]) == 10
    assert snap["elements_truncated"] is True
    await post(c, "/nav", url=f"{server}/big")
    snap = (await post(c, "/snapshot")).json()
    assert len(snap["text"]) <= 200
    assert snap["text_truncated"] is True
    ex = (await post(c, "/extract")).json()
    assert len(ex["markdown"]) <= 300


async def test_action_timeout(make, server: str) -> None:
    c = await make(action_timeout_ms=300)
    await post(c, "/nav", url=f"{server}/form")
    r = await post(c, "/click", selector="text=Hidden")
    assert r.status_code == 504
    assert r.json()["error"] == "timeout"


async def test_session_isolation(make, server: str) -> None:
    a = await make(session="alice")
    b = await make(session="bob")
    await post(a, "/nav", url=f"{server}/form")
    await post(b, "/nav", url=f"{server}/page2")
    assert (await post(a, "/snapshot")).json()["title"] == "Fixture Form"
    assert (await post(b, "/snapshot")).json()["title"] == "Second"
    assert len((await a.get("/tabs")).json()["tabs"]) == 1
    assert (await a.post("/close", json={})).json()["closed"] is True
    assert (await post(b, "/snapshot")).json()["title"] == "Second"


async def test_session_isolation_same_app(make, server: str) -> None:
    c = await make()
    await post(c, "/nav", url=f"{server}/form")
    other = {"X-Session-Id": "other"}
    snap = (await c.post("/snapshot", json={}, headers=other)).json()
    assert snap["url"] == "about:blank"
    cookie = await c.post("/nav", json={"url": f"{server}/page2"}, headers=other)
    assert cookie.status_code == 200
    assert (await post(c, "/snapshot")).json()["title"] == "Fixture Form"


async def test_max_contexts_cap(make, server: str) -> None:
    c = await make(max_contexts=2)
    for name in ("a", "b"):
        r = await c.post("/snapshot", json={}, headers={"X-Session-Id": name})
        assert r.status_code == 200
    r = await c.post("/snapshot", json={}, headers={"X-Session-Id": "c"})
    assert r.status_code == 429
    assert r.json()["error"] == "too_many_sessions"
    await c.post("/close", json={}, headers={"X-Session-Id": "a"})
    r = await c.post("/snapshot", json={}, headers={"X-Session-Id": "c"})
    assert r.status_code == 200


async def test_idle_contexts_reaped() -> None:
    now = [0.0]
    app = create_app(
        Settings(unsafe_allow_loopback=True, idle_minutes=1), clock=lambda: now[0]
    )
    mgr = app.state.manager
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            for name in ("old", "fresh"):
                await c.post("/snapshot", json={}, headers={"X-Session-Id": name})
            now[0] = 50
            await c.post("/snapshot", json={}, headers={"X-Session-Id": "fresh"})
            now[0] = 100
            assert await mgr.reap() == ["old"]
            assert set(mgr.sessions) == {"fresh"}
            assert (await c.get("/health")).json()["sessions"] == 1
    finally:
        await mgr.shutdown()


async def test_persistent_profile_dir(make, server: str, tmp_path) -> None:
    c = await make(profiles_dir=tmp_path / "profiles", session="p1")
    assert (await post(c, "/nav", url=f"{server}/form")).status_code == 200
    assert (tmp_path / "profiles" / "p1").is_dir()


def test_production_factory_refuses_an_empty_token(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(token=None))
    with pytest.raises(RuntimeError, match="DOT_BROWSER_TOKEN"):
        main.app_factory()
