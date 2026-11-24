from httpx import AsyncClient


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["x-request-id"]


async def test_ready_hits_db(client: AsyncClient):
    r = await client.get("/ready")
    assert r.status_code == 200


async def test_unknown_route_uses_envelope(client: AsyncClient):
    r = await client.get("/nope", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
    assert r.status_code == 404
    body = r.json()
    assert body[0]["code"] == 1002
    assert body[0]["messages"] == ["Не найдено"]
    assert set(body[0]) == {"key", "code", "show", "icon_type", "type", "messages"}


async def test_language_falls_back_to_english(client: AsyncClient):
    r = await client.get("/nope", headers={"Accept-Language": "fr"})
    assert r.json()[0]["messages"] == ["Not found"]


async def test_request_id_echoed_and_sanitised(client: AsyncClient):
    r = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    r = await client.get("/health", headers={"X-Request-ID": "bad id\twith space"})
    assert r.headers["x-request-id"] != "bad id\twith space"


async def test_wrong_method_is_405_envelope(client: AsyncClient):
    r = await client.post("/health")
    assert r.status_code == 405
    assert r.json()[0]["code"] == 1006
