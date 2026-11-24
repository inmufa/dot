import logging
from collections.abc import AsyncIterator

import pytest
from backend.core.api.auth import protected_router
from backend.core.api.envelope import build_envelope
from backend.core.error_messages import CATALOG, LANGUAGES
from backend.core.exceptions import DomainException
from backend.main import create_app
from backend.routing.clients.sandbox_client import SandboxClient
from backend.routing.clients.scripted import ScriptedLLM
from backend.settings import Settings
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel


class Item(BaseModel):
    name: str
    qty: int


@pytest.fixture
async def app_client(
    settings: Settings, llm: ScriptedLLM, sandbox: SandboxClient
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings, llm=llm, sandbox=sandbox)
    router = protected_router(prefix="/api")

    @router.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    @router.post("/items")
    async def items(item: Item) -> dict[str, str]:
        return {"name": item.name}

    @router.get("/domain")
    async def domain() -> None:
        raise DomainException(3002)

    @router.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")  # noqa: EM101

    app.include_router(router)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


AUTH = {"Authorization": "Bearer " + "t" * 32}


async def test_protected_route_rejects_missing_token(app_client: AsyncClient):
    r = await app_client.get("/api/ping")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()[0]["code"] == 1001


@pytest.mark.parametrize(
    "header", ["Bearer wrong", "Basic " + "t" * 32, "t" * 32, "Bearer "]
)
async def test_protected_route_rejects_bad_token(app_client: AsyncClient, header):
    r = await app_client.get("/api/ping", headers={"Authorization": header})
    assert r.status_code == 401


async def test_protected_route_accepts_token(app_client: AsyncClient):
    r = await app_client.get("/api/ping", headers=AUTH)
    assert r.status_code == 200


async def test_health_and_ready_stay_open(app_client: AsyncClient):
    assert (await app_client.get("/health")).status_code == 200
    assert (await app_client.get("/ready")).status_code == 200


async def test_domain_exception_mapped(app_client: AsyncClient):
    r = await app_client.get("/api/domain", headers={**AUTH, "Accept-Language": "uz"})
    assert r.status_code == 409
    assert r.json()[0]["code"] == 3002
    assert "Read" in r.json()[0]["messages"][0]


async def test_validation_one_entry_per_field(app_client: AsyncClient):
    r = await app_client.post("/api/items", headers=AUTH, json={"qty": "x"})
    assert r.status_code == 422
    body = r.json()
    assert {e["key"] for e in body} == {"name", "qty"}
    assert all(e["code"] == 1003 and e["type"] == "validation_error" for e in body)


async def test_unhandled_error_does_not_leak(
    app_client: AsyncClient, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.ERROR):
        r = await app_client.get("/api/boom", headers={**AUTH, "X-Request-ID": "rid-1"})
    assert r.status_code == 500
    assert r.json()[0]["code"] == 1000
    assert "secret internal detail" not in r.text
    assert r.headers["x-request-id"] == "rid-1"
    assert any(getattr(rec, "request_id", None) == "rid-1" for rec in caplog.records)


async def test_ready_returns_503_when_db_down(app_client: AsyncClient):
    app = app_client._transport.app  # type: ignore[attr-defined]
    await app.state.engine.dispose()
    app.state.engine = object()  # any use raises
    r = await app_client.get("/ready")
    assert r.status_code == 503
    assert r.json()[0]["code"] == 1008
    assert r.headers["retry-after"]


def test_every_code_translated_in_every_language():
    for code, entry in CATALOG.items():
        for lang in LANGUAGES:
            assert entry["messages"].get(lang), f"{code} missing {lang}"


def test_codes_in_range():
    assert all(1000 <= code < 5000 for code in CATALOG)


def test_status_valid_and_show_flag():
    for code, entry in CATALOG.items():
        assert 400 <= entry["status"] < 600, code
        assert isinstance(entry["show"], bool), code


def test_unknown_code_falls_back_to_1000():
    status, body = build_envelope(99999, "en")
    assert (status, body["code"]) == (500, 1000)
