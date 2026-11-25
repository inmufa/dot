import logging
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from backend.core.exceptions import DomainException
from backend.routing.clients.scripted import reply
from backend.vault import sessionstate
from backend.vault.models import VaultCredential
from conftest import COOKIE_VALUE, PASSWORD, SITE, make_cred
from helpers import new_session
from sqlalchemy import update
from test_login_tool import SEARCH, result, run

LOGIN = ("BrowserLogin", {"credential": "ex"})


async def login_once(authed, app, llm):
    await run(authed, app, llm, "default", ["allow"])


async def edit(app, **values):
    async with app.state.vault.svc._maker() as db:
        await db.execute(update(VaultCredential).values(**values))
        await db.commit()


def raw_row(app, cred_id):
    return app.state.vault.svc.row(cred_id)


async def test_login_saves_scoped_encrypted_session(authed, app, llm, worker, caplog):
    caplog.set_level(logging.DEBUG)
    made = await make_cred(authed)
    await login_once(authed, app, llm)
    (item,) = (await authed.get("/v1/vault")).json()
    assert item["has_session"] is True
    assert item["session_saved_at"]
    assert item["session_expires_at"]
    assert COOKIE_VALUE not in str((await authed.get("/v1/vault")).text)
    row = await raw_row(app, made["id"])
    assert COOKIE_VALUE.encode() not in row.session_blob
    state = await app.state.vault.svc.load_session(row)
    assert [c["domain"] for c in state["cookies"]] == [
        "example.com"
    ]  # tracker cookie dropped
    assert COOKIE_VALUE not in caplog.text


async def test_saved_session_is_restored_instead_of_typing_the_password(
    authed, app, llm, worker
):
    await make_cred(authed)
    await login_once(authed, app, llm)
    worker.calls.clear()
    worker.restored.clear()
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert "saved session restored" in result(ev)["output"]
    assert "/vault/login" not in worker.paths()
    body = next(b for p, b in worker.calls if p == "/vault/session/restore")
    assert (
        body["state"]["cookies"][0]["value"] == COOKIE_VALUE
    )  # only the worker gets it
    assert body["origins"] == [SITE]


async def test_dead_session_falls_back_to_password_and_is_cleared(
    authed, app, llm, worker
):
    made = await make_cred(authed)
    await login_once(authed, app, llm)
    worker.login_form = True
    worker.calls.clear()
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert result(ev)["output"].startswith("logged in")
    assert "/vault/login" in worker.paths()
    assert (
        await raw_row(app, made["id"])
    ).session_blob is not None  # re-saved after the new login


async def test_expired_session_is_dropped_never_restored(authed, app, llm, worker):
    made = await make_cred(authed)
    await login_once(authed, app, llm)
    await edit(app, session_expires_at=datetime.now(UTC) - timedelta(days=1))
    worker.calls.clear()
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert "/vault/session/restore" not in worker.paths()
    assert "/vault/login" in worker.paths()
    assert result(ev)["output"].startswith("logged in")
    assert made["id"]


async def test_session_only_entry_expired_says_login_needed(authed, app, llm, worker):
    await authed.post("/v1/vault", json={"label": "ex", "origins": [SITE]})
    _, ev = await run(authed, app, llm, "default", ["allow"])
    out = result(ev)["output"]
    assert out.startswith("failed:")
    assert "expired" in out
    assert "/vault/login" not in worker.paths()


async def test_tampered_blobs_fail_closed(authed, app, llm, worker):
    made = await make_cred(authed)
    await login_once(authed, app, llm)
    row = await raw_row(app, made["id"])
    bad = bytearray(row.session_blob)
    bad[20] ^= 1
    await edit(app, session_blob=bytes(bad))
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert "4147" in result(ev)["output"]
    worker.calls.clear()
    bad = bytearray(row.secret_blob)
    bad[20] ^= 1
    await edit(app, secret_blob=bytes(bad), session_blob=None)
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert "4147" in result(ev)["output"]
    assert "/vault/login" not in worker.paths()


async def test_moved_blob_does_not_open_under_another_record(authed, app, llm, worker):
    a = await make_cred(authed)
    b = await make_cred(authed, label="b", origins=["https://b.org"])
    ra = await raw_row(app, a["id"])
    await edit(app, secret_blob=ra.secret_blob)  # same blob on every row
    with pytest.raises(DomainException) as exc:
        app.state.vault.svc.secrets(await raw_row(app, b["id"]))
    assert exc.value.code == 4147


def chat_nav(authed, llm, sid, url):
    llm.scripts = [
        reply(calls=[SEARCH]),
        reply(calls=[("BrowserNavigate", {"url": url})]),
        reply("ok"),
    ]
    return authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})


async def test_agent_navigation_restores_only_after_consent_and_only_for_bound_origin(
    authed, app, llm, worker
):
    await make_cred(authed)
    await run(authed, app, llm, "bypass", ["allow"])  # consent for this credential
    other = await new_session(authed, "bypass")
    worker.calls.clear()
    worker.restored.clear()
    await chat_nav(authed, llm, other, f"{SITE}/x")  # no consent in this Dot session
    assert "/vault/session/restore" not in worker.paths()
    sid = next(iter(app.state.vault.consent))
    await chat_nav(authed, llm, sid, "https://other.org/")  # consented, wrong origin
    await chat_nav(authed, llm, sid, "https://example.com.evil.net/")
    assert "/vault/session/restore" not in worker.paths()
    worker.restored.clear()
    await chat_nav(authed, llm, sid, f"{SITE}/x")
    assert worker.paths().count("/vault/session/restore") == 1
    await chat_nav(authed, llm, sid, f"{SITE}/y")  # already restored in this context
    assert worker.paths().count("/vault/session/restore") == 1


async def test_owner_navigation_restores_without_prompt(authed, app, llm, worker):
    await make_cred(authed)
    await login_once(authed, app, llm)
    sid = await new_session(authed)
    worker.restored.clear()
    worker.calls.clear()
    for _ in range(2):
        r = await authed.post(
            f"/v1/sessions/{sid}/browser/navigate", json={"url": f"{SITE}/home"}
        )
        assert r.status_code == 200, r.text
    assert worker.paths().count("/vault/session/restore") == 1
    r = await authed.post(
        f"/v1/sessions/{sid}/browser/navigate", json={"url": "https://elsewhere.org/"}
    )
    assert worker.paths().count("/vault/session/restore") == 1
    assert COOKIE_VALUE not in r.text


def test_tidy_rules():
    now = time.time()
    raw = {
        "cookies": [
            {"name": "a", "value": "1", "domain": "example.com", "expires": now - 5},
            {
                "name": "b",
                "value": "2",
                "domain": "example.com",
                "expires": now + 10 * 86400,
            },
            {
                "name": "c",
                "value": "3",
                "domain": ".example.com",
                "expires": now + 400 * 86400,
            },
            {"name": "d", "value": "4", "domain": "example.com", "expires": -1},
            {"name": "e", "value": "5", "domain": "evil.com", "expires": -1},
        ],
        "origins": [
            {"origin": SITE, "localStorage": [{"name": "k", "value": "v"}]},
            {
                "origin": "https://evil.com",
                "localStorage": [{"name": "k", "value": "v"}],
            },
        ],
    }
    state, latest = sessionstate.tidy(raw, [SITE], 30, now)
    names = {c["name"]: c["expires"] for c in state["cookies"]}
    assert set(names) == {"b", "c", "d"}
    assert names["c"] == now + 30 * 86400  # capped
    assert names["d"] == now + 30 * 86400  # session cookie made persistent, capped
    assert latest == now + 30 * 86400
    assert [o["origin"] for o in state["origins"]] == [SITE]
    dead = sessionstate.tidy({"cookies": raw["cookies"][:1]}, [SITE], 30, now)
    assert dead == ({"cookies": [], "origins": []}, None)


async def test_save_session_from_owner_new_entry_and_attach(authed, app, worker):
    sid = await new_session(authed)
    r = await authed.post(
        "/v1/vault/save-session", json={"session_id": sid, "label": "manual"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["origins"] == [SITE]
    assert r.json()["has_session"] is True
    assert r.json()["has_password"] is False
    assert COOKIE_VALUE not in r.text
    made = await make_cred(authed, label="pw", origins=["https://login.example.com"])
    r = await authed.post(
        "/v1/vault/save-session", json={"session_id": sid, "credential": made["id"]}
    )
    assert r.json()["origins"] == [
        "https://login.example.com",
        SITE,
    ]  # owner action binds the site
    assert (await app.state.vault.svc.row(made["id"])).session_blob is not None


async def test_save_session_errors(authed, app, worker):
    sid = await new_session(authed)
    worker.page = "about:blank"
    r = await authed.post(
        "/v1/vault/save-session", json={"session_id": sid, "label": "x"}
    )
    assert r.json()[0]["code"] == 4150
    worker.page = "https://nocookies.org/"
    r = await authed.post(
        "/v1/vault/save-session", json={"session_id": sid, "label": "y"}
    )
    assert r.json()[0]["code"] == 4151
    r = await authed.post(
        "/v1/vault/save-session", json={"session_id": "Snope0000", "label": "z"}
    )
    assert r.status_code == 404


async def test_clear_one_and_clear_all(authed, app, llm, worker):
    a = await make_cred(authed)
    await login_once(authed, app, llm)
    assert (await authed.delete(f"/v1/vault/{a['id']}/session")).json() == {"ok": True}
    assert (await authed.get("/v1/vault")).json()[0]["has_session"] is False
    assert (await authed.delete("/v1/vault/nope/session")).status_code == 404
    await login_once(authed, app, llm)
    r = await authed.delete("/v1/vault/sessions")
    assert r.json()[0]["code"] == 4143
    assert (await authed.delete("/v1/vault/sessions?confirm=all")).json() == {
        "cleared": 1
    }
    assert (await authed.get("/v1/vault")).json()[0]["has_session"] is False


async def test_origin_change_drops_the_session(authed, app, llm, worker):
    a = await make_cred(authed)
    await login_once(authed, app, llm)
    r = await authed.patch(
        f"/v1/vault/{a['id']}", json={"origins": ["https://other.org"]}
    )
    assert r.json()["has_session"] is False
    assert r.json()["has_password"] is True


async def test_refresh_resaves_live_sessions_and_forgets_dead_ones(
    authed, app, llm, worker
):
    a = await make_cred(authed)
    await login_once(authed, app, llm)
    before = (await raw_row(app, a["id"])).session_saved_at
    worker.calls.clear()
    await app.state.vault.refresh()
    assert "/vault/session/export" in worker.paths()
    assert (await raw_row(app, a["id"])).session_saved_at >= before
    app.state.vault.worker._b._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(404, json={"error": "no_session", "detail": "x"})
        )
    )
    await app.state.vault.refresh()
    assert not app.state.vault.live


async def test_no_cookie_value_anywhere_public(authed, app, llm, worker, caplog):
    caplog.set_level(logging.DEBUG)
    await make_cred(authed)
    await login_once(authed, app, llm)
    sid = await new_session(authed)
    await authed.post(
        f"/v1/sessions/{sid}/browser/navigate", json={"url": f"{SITE}/home"}
    )
    await authed.post("/v1/vault/save-session", json={"session_id": sid, "label": "m"})
    blob = (
        (await authed.get("/v1/vault")).text
        + (await authed.get("/v1/audit")).text
        + caplog.text
    )
    for s in (COOKIE_VALUE, PASSWORD):
        assert s not in blob
