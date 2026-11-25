import json
import logging
from pathlib import Path

import httpx
import pytest
from backend.routing.clients.scripted import reply
from conftest import COOKIE_VALUE, PASSWORD, SITE, TOTP, make_cred
from fastapi import FastAPI
from helpers import new_session, parse_sse, resolve_next, start_chat, types
from httpx import AsyncClient

CALL = ("BrowserLogin", {"credential": "ex"})
SEARCH = ("ToolSearch", {"query": "select:BrowserLogin,BrowserNavigate"})


async def run(authed, app, llm, mode, decisions, calls=(CALL,), *, sid=None):  # noqa: PLR0913
    """One chat turn; `decisions` are answered to each approval in order."""
    llm.scripts = [reply(calls=[SEARCH]), reply(calls=list(calls)), reply("done")]
    sid = sid or await new_session(authed, mode)
    task = start_chat(authed, sid)
    for d in decisions:
        await resolve_next(app, authed, d)
    return sid, parse_sse((await task).text)


def result(events):
    return [e["result"] for e in events if e["type"] == "tool_result"][-1]


async def everything(authed, sid, events, caplog) -> str:
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).text
    audit = (await authed.get("/v1/audit")).text
    return (
        json.dumps(events)
        + msgs
        + audit
        + caplog.text
        + (await authed.get("/v1/vault")).text
    )


@pytest.mark.parametrize("mode", ["default", "acceptEdits", "auto", "bypass"])
async def test_always_asks_in_every_mode(authed, app, llm, worker, mode):
    await make_cred(authed)
    _, ev = await run(authed, app, llm, mode, ["allow"])
    assert "approval_required" in types(ev)
    assert result(ev)["output"].startswith("logged in")


async def test_plan_mode_denies(authed, app, llm, worker):
    await make_cred(authed)
    _, ev = await run(authed, app, llm, "plan", [])
    assert result(ev)["is_error"]
    assert worker.calls == []


async def test_reject_never_reaches_the_worker(authed, app, llm, worker):
    await make_cred(authed)
    _, ev = await run(authed, app, llm, "default", ["reject"])
    assert result(ev)["is_error"]
    assert not any(p.startswith("/vault/login") for p in worker.paths())


async def test_allow_rule_and_hooks_do_not_skip_the_prompt(
    authed, app, llm, worker, ws: Path
):
    await make_cred(authed)
    (ws / ".dot").mkdir(exist_ok=True)
    (ws / ".dot" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["BrowserLogin"]}})
    )
    _, ev = await run(authed, app, llm, "bypass", ["reject"])
    assert "approval_required" in types(ev)
    assert result(ev)["is_error"]


async def test_deny_rule_still_denies(authed, app, llm, worker, ws: Path):
    await make_cred(authed)
    (ws / ".dot").mkdir(exist_ok=True)
    (ws / ".dot" / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["BrowserLogin"]}})
    )
    _, ev = await run(authed, app, llm, "default", [])
    assert "approval_required" not in types(ev)
    assert result(ev)["is_error"]


async def test_approval_card_shows_site_user_label_not_secret(authed, app, llm, worker):
    await make_cred(authed)
    _, ev = await run(authed, app, llm, "default", ["allow"])
    (card,) = [e for e in ev if e["type"] == "approval_required"]
    text = json.dumps(card)
    for needle in (SITE, "alice", "ex"):
        assert needle in text
    assert PASSWORD not in text
    assert TOTP not in text


async def test_always_is_scoped_to_one_login_and_one_session(authed, app, llm, worker):
    await make_cred(authed)
    await make_cred(authed, label="other", origins=["https://other.org"])
    sid, _ = await run(authed, app, llm, "default", ["always"])
    _, ev = await run(authed, app, llm, "default", [], sid=sid)
    assert "approval_required" not in types(ev)  # same login, same session
    _, ev = await run(
        authed,
        app,
        llm,
        "default",
        ["reject"],
        calls=[("BrowserLogin", {"credential": "other"})],
        sid=sid,
    )
    assert "approval_required" in types(ev)  # another login still asks
    _, ev = await run(authed, app, llm, "default", ["reject"])  # new session asks again
    assert "approval_required" in types(ev)


async def test_secret_reaches_only_the_worker(authed, app, llm, worker, caplog):
    caplog.set_level(logging.DEBUG)
    await make_cred(authed)
    sid, ev = await run(authed, app, llm, "default", ["allow"])
    body = next(b for p, b in worker.calls if p == "/vault/login")
    assert body["password"] == PASSWORD
    assert body["totp_secret"] == TOTP
    out = result(ev)
    assert out["tainted"] is True
    assert out["output"].startswith("logged in")
    blob = await everything(authed, sid, ev, caplog)
    for s in (PASSWORD, TOTP, COOKIE_VALUE):
        assert s not in blob


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("wrong_credentials", "wrong credentials"),
        ("captcha", "captcha"),
        ("2fa_required", "second factor"),
        ("form_not_found", "no login form"),
    ],
)
async def test_failures_are_coarse(authed, app, llm, worker, outcome, reason):
    await make_cred(authed)
    worker.outcome = outcome
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert result(ev)["output"].startswith("failed:")
    assert reason in result(ev)["output"]


async def test_url_outside_bound_origin_refused_before_the_worker(
    authed, app, llm, worker
):
    await make_cred(authed)
    for url in (
        "https://evil-example.com/login",
        "https://example.com.evil.net/",
        "https://xn--exmple-cua.com/",
        "http://example.com/",
    ):
        worker.calls.clear()
        _, ev = await run(
            authed,
            app,
            llm,
            "bypass",
            ["allow"],
            calls=[("BrowserLogin", {"credential": "ex", "url": url})],
        )
        out = result(ev)
        assert out["is_error"]
        assert "4144" in out["output"]
        assert worker.calls == []


async def test_worker_refusals_map_to_codes(authed, app, llm, worker):
    await make_cred(authed)

    def refuse(req):
        return httpx.Response(
            403, json={"error": "unsafe_form", "detail": "form posts to another origin"}
        )

    app.state.vault.worker._b._client = httpx.AsyncClient(
        transport=httpx.MockTransport(refuse)
    )
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert "4148" in result(ev)["output"]
    app.state.vault.worker._b._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                403, json={"error": "origin_mismatch", "detail": "x"}
            )
        )
    )
    _, ev = await run(authed, app, llm, "default", ["allow"])
    assert "4144" in result(ev)["output"]


async def test_login_rate_limited_per_credential(authed, app, llm, worker):
    await make_cred(authed)
    worker.outcome = "wrong_credentials"
    sid = await new_session(authed, "default")
    outs = []
    for _ in range(5):
        _, ev = await run(
            authed, app, llm, "default", ["always"] if not outs else [], sid=sid
        )
        outs.append(result(ev)["output"])
    assert any("4145" in o for o in outs)


async def test_unknown_label_and_vault_off_are_errors(authed, app, llm, worker):
    _, ev = await run(
        authed,
        app,
        llm,
        "bypass",
        ["allow"],
        calls=[("BrowserLogin", {"credential": "nope"})],
    )
    assert "4141" in result(ev)["output"]


async def test_tool_is_deferred_mutating_and_listed(authed, app: FastAPI):
    by = {t["name"]: t for t in (await authed.get("/v1/tools")).json()}
    assert by["BrowserLogin"]["deferred"] is True
    assert by["BrowserLogin"]["mutating"] is True
    assert "BrowserLogin" not in {
        d.name for d in app.state.agent.registry.core_definitions()
    }
    desc = by["BrowserLogin"]["description"]
    assert "never see" in desc


async def test_audit_use_row_has_label_origin_outcome(authed, app, llm, worker):
    await make_cred(authed)
    await run(authed, app, llm, "default", ["allow"])
    text = (await authed.get("/v1/audit")).text
    assert "vault.use" in text
    assert "logged_in" in text


async def test_navigate_hint_lists_labels_only(authed: AsyncClient, app, llm, worker):
    await make_cred(authed)
    sid = await new_session(authed, "bypass")
    nav = ("BrowserNavigate", {"url": f"{SITE}/login"})
    llm.scripts = [reply(calls=[SEARCH]), reply(calls=[nav]), reply("ok")]
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    out = result(ev)["output"]
    assert "'ex'" in out
    assert PASSWORD not in out
