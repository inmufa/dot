import httpx
from conftest import Make


async def post(c: httpx.AsyncClient, path: str, **body: object) -> httpx.Response:
    return await c.post(path, json=body)


async def test_state_and_frame_do_not_launch_a_session(
    client: httpx.AsyncClient,
) -> None:
    st = (await client.get("/view/state")).json()
    assert st["open"] is False
    assert (await post(client, "/view/frame")).status_code == 204
    assert (await client.get("/health")).json()["sessions"] == 0


async def test_frame_is_a_capped_jpeg(client: httpx.AsyncClient, server: str) -> None:
    await post(client, "/nav", url=f"{server}/form")
    r = await post(client, "/view/frame", quality=40)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    st = (await client.get("/view/state")).json()
    assert st["open"]
    assert st["title"] == "Fixture Form"
    assert st["viewport"]["width"] == 1280
    assert st["loading"] is False


async def test_frame_over_cap_is_413(make: Make, server: str) -> None:
    c = await make(max_frame_bytes=100)
    await post(c, "/nav", url=f"{server}/form")
    r = await post(c, "/view/frame")
    assert r.status_code == 413
    assert r.json()["error"] == "frame_too_large"


async def test_click_by_coordinates_wheel_type_forward_reload(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    snap = (await post(client, "/snapshot")).json()
    assert snap["elements"]
    # the link "Next page" sits near the top-left of the fixture page
    for y in range(40, 200, 8):
        r = await post(client, "/view/click", x=30, y=y)
        if r.json()["url"].endswith("/page2"):
            break
    assert r.json()["url"].endswith("/page2")
    await post(client, "/back")
    fwd = await post(client, "/view/forward")
    assert fwd.json()["url"].endswith("/page2")
    assert (await post(client, "/view/reload")).json()["title"] == "Second"
    assert (await post(client, "/view/wheel", x=10, y=10, dy=200)).status_code == 200
    await post(client, "/nav", url=f"{server}/form")
    snap = (await post(client, "/snapshot")).json()
    q = next(e for e in snap["elements"] if e["name"] == "Query")["id"]
    await post(client, "/click", element_id=q)
    assert (await post(client, "/view/type", text="abc")).status_code == 200
    snap = (await post(client, "/snapshot")).json()
    assert next(e for e in snap["elements"] if e["name"] == "Query")["value"] == "abc"


async def test_click_outside_viewport_rejected(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    r = await post(client, "/view/click", x=9000, y=10)
    assert r.status_code == 422
    assert r.json()["error"] == "out_of_view"


async def test_viewport_follows_owner_and_is_clamped(
    client: httpx.AsyncClient, server: str
) -> None:
    # before any page: remembered, no Chromium launched, new context starts at it
    r = await post(client, "/view/viewport", width=536, height=700)
    assert r.json()["viewport"] == {"width": 536, "height": 700}
    assert (await client.get("/health")).json()["sessions"] == 0
    st = (await client.get("/view/state")).json()
    assert st["open"] is False
    assert st["viewport"] == {"width": 536, "height": 700}
    await post(client, "/nav", url=f"{server}/form")
    st = (await client.get("/view/state")).json()
    assert st["viewport"] == {"width": 536, "height": 700}
    # live resize, clamped to bounds; new tabs inherit it
    r = await post(client, "/view/viewport", width=100, height=9000)
    assert r.json()["viewport"] == {"width": 320, "height": 1600}
    st = (await client.get("/view/state")).json()
    assert st["viewport"] == {"width": 320, "height": 1600}
    await post(client, "/tabs/new", url=f"{server}/page2")
    st = (await client.get("/view/state")).json()
    assert st["viewport"] == {"width": 320, "height": 1600}
    shot = await post(client, "/view/frame")
    assert shot.status_code == 200
    assert (await post(client, "/view/viewport", width=0, height=10)).status_code == 422


async def test_history_flags_and_owner_back(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    st = (await client.get("/view/state")).json()
    assert st["can_back"] is False
    assert st["can_forward"] is False
    await post(client, "/nav", url=f"{server}/page2")
    st = (await client.get("/view/state")).json()
    assert st["can_back"] is True
    assert st["can_forward"] is False
    r = await post(client, "/view/back")
    assert r.json()["moved"] is True
    st = (await client.get("/view/state")).json()
    assert st["url"].endswith("/form")
    assert st["can_forward"] is True


async def test_owner_nav_can_return_at_commit(
    client: httpx.AsyncClient, server: str
) -> None:
    r = await post(client, "/nav", url=f"{server}/page2", wait_until="commit")
    assert r.status_code == 200
    assert r.json()["status"] == 200
    r = await post(client, "/tabs/new", url=f"{server}/form", wait_until="commit")
    assert r.status_code == 200
