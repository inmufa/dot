import asyncio
import json
import logging

import pytest
from backend.core.api.ratelimit import TokenBucket
from backend.core.logging import register_secret, setup_logging
from backend.main import create_app
from backend.routing.clients.scripted import ScriptedLLM
from backend.settings import Settings
from helpers import new_session, until
from httpx import ASGITransport, AsyncClient

AUTH = {"Authorization": "Bearer " + "t" * 32}


def test_bucket_refills_and_reports_wait():
    now = [0.0]
    bucket = TokenBucket(60, 2, clock=lambda: now[0])  # 1 token per second
    assert bucket.take("a") == 0
    assert bucket.take("a") == 0
    assert bucket.take("a") == pytest.approx(1.0)
    assert bucket.take("b") == 0  # separate client
    now[0] = 1.0
    assert bucket.take("a") == 0


async def test_message_too_long_is_1010(app, authed: AsyncClient):
    sid = await new_session(authed)
    app.state.settings.max_message_chars = 10
    r = await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "x" * 11})
    assert r.status_code == 413
    assert r.json()[0]["code"] == 1010


async def test_body_over_content_length_is_413_1011(app, authed: AsyncClient):
    big = b"{" + b" " * (app.state.settings.max_body_bytes + 10) + b"}"
    r = await authed.post(
        "/v1/sessions", content=big, headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()[0]["code"] == 1011


async def test_chunked_body_over_limit_is_413(app, authed: AsyncClient):
    limit = app.state.settings.max_body_bytes

    async def chunks():
        for _ in range(limit // 1024 + 2):
            yield b" " * 1024

    r = await authed.post(
        "/v1/sessions", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()[0]["code"] == 1011


async def test_chat_rate_limit_returns_1004_with_retry_after(
    settings: Settings, sandbox
):
    cfg = settings.model_copy(update={"chat_rate_burst": 2, "chat_rate_per_min": 1})
    app = create_app(cfg, llm=ScriptedLLM([]), sandbox=sandbox)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", headers=AUTH
        ) as c,
    ):
        sid = await new_session(c)
        codes = []
        for _ in range(3):
            r = await c.post(f"/v1/sessions/{sid}/chat", json={"message": "hi"})
            codes.append(r.status_code)
            await until(lambda: not app.state.turns.is_active(sid))
        assert codes == [200, 200, 429]
        assert r.json()[0]["code"] == 1004
        assert int(r.headers["retry-after"]) >= 1


async def test_unauthenticated_chat_does_not_spend_tokens(app, client: AsyncClient):
    for _ in range(20):
        r = await client.post("/v1/sessions/S1/chat", json={"message": "hi"})
        assert r.status_code == 401


async def test_security_headers_everywhere(authed: AsyncClient, client: AsyncClient):
    for r in (await client.get("/health"), await authed.get("/v1/sessions")):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert "default-src 'none'" in r.headers["content-security-policy"]
    assert (await authed.get("/v1/sessions")).headers["cache-control"] == "no-store"
    err = await client.get("/nope")
    assert err.headers["x-content-type-options"] == "nosniff"


async def test_cors_is_closed(app, client: AsyncClient):
    assert all("CORS" not in m.cls.__name__ for m in app.user_middleware)
    r = await client.options(
        "/v1/sessions",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "GET"},
    )
    assert not any(h.lower().startswith("access-control-") for h in r.headers)
    r = await client.get("/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in r.headers


async def test_token_never_reaches_logs(
    app, client: AsyncClient, caplog: pytest.LogCaptureFixture, capsys
):
    token = app.state.settings.api_token
    register_secret(token)
    caplog.set_level(logging.DEBUG)
    await client.get("/v1/sessions", headers={"Authorization": "Bearer " + "z" * 32})
    await client.get("/v1/sessions", headers=AUTH)
    logging.getLogger("x").warning("leaky %s", token)
    out = capsys.readouterr()
    everything = caplog.text + out.out + out.err
    assert token not in everything
    assert "z" * 32 not in everything


def test_json_log_line_masks_registered_secret(capsys):
    setup_logging(as_json=True)
    register_secret("s3cretvalue-123")
    logging.getLogger("t").error(
        "boom s3cretvalue-123", exc_info=ValueError("s3cretvalue-123")
    )
    line = capsys.readouterr().out
    assert "s3cretvalue-123" not in line
    assert json.loads(line.splitlines()[0])["message"] == "boom ***"


async def test_shutdown_cancels_running_turn(settings: Settings, sandbox):
    gate = asyncio.Event()  # never set: the turn blocks inside the model call
    llm = ScriptedLLM([[gate]])
    app = create_app(settings, llm=llm, sandbox=sandbox)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", headers=AUTH
        ) as c,
    ):
        sid = await new_session(c)
        task = asyncio.create_task(
            c.post(f"/v1/sessions/{sid}/chat", json={"message": "hi"})
        )
        await until(lambda: bool(llm.requests))
        turns = app.state.turns
        assert turns.is_active(sid)
    await asyncio.wait_for(task, 5)
    assert not turns.is_active(sid)
