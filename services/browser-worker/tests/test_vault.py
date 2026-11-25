import httpx
import login_server as ls
import pytest
from dot_browser.vault import loginform
from dot_browser.vault.origin import cookie_in_scope, origin_matches, origin_of
from dot_browser.vault.totp import totp_code


@pytest.fixture(scope="module")
def site():
    httpd, base = ls.start()
    yield base
    httpd.shutdown()


async def login(
    c: httpx.AsyncClient, site: str, path: str, **kw: object
) -> httpx.Response:
    body = {
        "origins": [site],
        "username": ls.USER,
        "password": ls.PASSWORD,
        "url": f"{site}{path}",
        **kw,
    }
    return await c.post("/vault/login", json=body)


async def title(c: httpx.AsyncClient) -> str:
    return (await c.post("/snapshot", json={})).json()["title"]


async def test_one_step(client, site):
    r = await login(client, site, "/login1")
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "logged_in"
    assert r.json()["title"] == "Home"
    assert ls.PASSWORD not in r.text


async def test_two_step(client, site):
    r = await login(client, site, "/login2")
    assert r.json()["outcome"] == "logged_in", r.text


async def test_totp(client, site):
    r = await login(client, site, "/login-totp", totp_secret=ls.TOTP)
    assert r.json()["outcome"] == "logged_in", r.text
    assert ls.TOTP not in r.text


async def test_totp_needed_but_missing(client, site):
    r = await login(client, site, "/login-totp")
    assert r.json()["outcome"] == "2fa_required"


async def test_wrong_password(client, site):
    r = await login(client, site, "/login1", password="nope-nope-nope")
    assert r.json()["ok"] is False
    assert r.json()["outcome"] == "wrong_credentials"


async def test_captcha(client, site):
    assert (await login(client, site, "/captcha")).json()["outcome"] == "captcha"


async def test_no_form(client, site):
    assert (await login(client, site, "/plain")).json()["outcome"] == "form_not_found"


async def test_origin_mismatch_url_refused_before_navigation(client, site):
    other = site.replace("127.0.0.1", "localhost")
    r = await login(client, other, "/login1", origins=[site])
    assert r.status_code == 403
    assert r.json()["error"] == "origin_mismatch"


async def test_origin_mismatch_current_page(client, site):
    other = site.replace("127.0.0.1", "localhost")
    await client.post("/nav", json={"url": f"{other}/login1"})
    body = {"origins": [site], "username": ls.USER, "password": ls.PASSWORD}
    r = await client.post("/vault/login", json=body)
    assert r.status_code == 403
    assert r.json()["error"] == "origin_mismatch"
    assert ls.PASSWORD not in r.text


@pytest.mark.parametrize("path", ["/hidden", "/offaction", "/framed"])
async def test_odd_forms_refused(client, site, path):
    r = await login(client, site, path)
    assert r.status_code == 403, r.text
    assert r.json()["error"] == "unsafe_form"
    snap = (await client.post("/snapshot", json={})).json()
    assert ls.PASSWORD not in str(snap)


async def test_frames_masked_during_login_only(client, site):
    await login(client, site, "/login1")
    assert (await client.post("/view/frame", json={})).status_code == 200


async def test_token_required(make, site):
    c = await make(token="tok")
    r = await login(c, site, "/login1")
    assert r.status_code == 401


async def test_validation_error_does_not_echo_secret(client, site):
    r = await client.post(
        "/vault/login",
        json={"origins": [site], "username": "a", "password": "x" * 3000},
    )
    assert r.status_code == 422
    assert "xxxx" not in r.text


async def test_session_export_restore_in_new_context(make, site):
    a = await make(session="one")
    await login(a, site, "/login1")
    ex = await a.post("/vault/session/export", json={"origins": [site]})
    state = ex.json()
    assert any(c["name"] == "sid" for c in state["cookies"])
    b = await make(session="two")
    anon = await b.post("/nav", json={"url": f"{site}/home"})
    assert anon.json()["title"] == "Anon"
    r = await b.post(
        "/vault/session/restore",
        json={"id": "C1", "origins": [site], "state": state, "url": f"{site}/home"},
    )
    assert r.json()["restored"] == 1
    assert r.json()["login_form"] is False
    assert await title(b) == "Home"
    done = await b.post("/vault/session/restored", json={"ids": ["C1", "C2"]})
    assert done.json() == {"restored": ["C1"]}


async def test_export_filters_foreign_cookies_and_restore_refuses_other_origin(
    make, site
):
    a = await make(session="one")
    await login(a, site, "/login1")
    state = (await a.post("/vault/session/export", json={"origins": [site]})).json()
    state["cookies"].append(
        {"name": "x", "value": "y", "domain": "evil.test", "path": "/", "expires": -1}
    )
    b = await make(session="two")
    other = site.replace("127.0.0.1", "localhost")
    r = await b.post(
        "/vault/session/restore",
        json={"id": "C", "origins": [site], "state": state, "url": f"{other}/home"},
    )
    assert r.status_code == 403
    r = await b.post(
        "/vault/session/restore", json={"id": "C", "origins": [site], "state": state}
    )
    assert r.json()["restored"] == 1  # the evil.test cookie was dropped


async def test_export_without_context_is_404(client):
    r = await client.post("/vault/session/export", json={"origins": ["https://a.test"]})
    assert r.status_code == 404


def test_origin_rules():
    assert origin_of("HTTPS://Example.COM:443/x") == "https://example.com"
    assert origin_of("https://example.com@evil.net/") == "https://evil.net"
    assert origin_of("javascript:alert(1)") is None
    ok = ["https://example.com"]
    for bad in (
        "https://evil-example.com/",
        "https://example.com.evil.net/",
        "https://sub.example.com/",
        "http://example.com/",
        "https://example.com:8443/",
        "https://exаmple.com/",  # cyrillic a
        "https://xn--exmple-cua.com/",
    ):
        assert not origin_matches(bad, ok), bad
    assert origin_matches("https://EXAMPLE.com./a", ok)
    assert origin_matches("https://bücher.example/", ["https://xn--bcher-kva.example"])


def test_cookie_scope():
    o = ["https://app.example.com"]
    assert cookie_in_scope(".example.com", o)
    assert cookie_in_scope("app.example.com", o)
    assert not cookie_in_scope("evil.com", o)
    assert not cookie_in_scope("com", o)
    assert not cookie_in_scope("other.example.com", o)


def test_totp_rfc6238_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890"
    assert totp_code(secret, 59) == "287082"
    assert totp_code(secret, 1111111109) == "081804"


def _inp(i, **kw):
    base = {
        "i": i,
        "type": "text",
        "name": "",
        "id": "",
        "ac": "",
        "mode": "",
        "max": -1,
        "label": "",
        "form": 0,
        "actions": [],
        "visible": True,
    }
    return base | kw


def test_plan_variants():
    full = loginform.plan([_inp(0, type="email"), _inp(1, type="password")])
    assert (full.kind, full.user, full.password) == ("full", 0, 1)
    assert loginform.plan([_inp(0, type="password")]).kind == "password_only"
    assert loginform.plan([_inp(0, name="q"), _inp(1, name="user")]).user == 1
    assert loginform.plan([_inp(0, ac="one-time-code")]).kind == "otp"
    hid = loginform.plan([_inp(0, type="password", visible=False)])
    assert hid.kind == "none"
    assert hid.hidden_password
    assert (
        loginform.plan(
            [_inp(0, type="password", visible=False), _inp(1, type="email")]
        ).kind
        == "username_only"
    )
