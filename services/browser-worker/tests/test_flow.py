import base64

import httpx


async def post(c: httpx.AsyncClient, path: str, **body: object) -> httpx.Response:
    return await c.post(path, json=body)


def by_name(snap: dict, name: str) -> dict:
    return next(e for e in snap["elements"] if e["name"] == name)


async def test_health_and_nav_snapshot(client: httpx.AsyncClient, server: str) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    r = await post(client, "/nav", url=f"{server}/form")
    assert r.status_code == 200
    nav = r.json()
    assert nav["title"] == "Fixture Form"
    assert nav["tainted"] is True
    assert nav["status"] == 200
    snap = (await post(client, "/snapshot")).json()
    assert snap["tainted"] is True
    assert snap["url"].endswith("/form")
    assert "Welcome page" in snap["text"]
    names = {e["name"] for e in snap["elements"]}
    assert {"Next page", "Query", "Search", "Press me", "Color"} <= names
    assert "Hidden" not in names
    assert by_name(snap, "Next page")["role"] == "link"
    assert by_name(snap, "Next page")["href"].endswith("/page2")
    assert by_name(snap, "Query")["role"] == "textbox"
    assert by_name(snap, "Color")["role"] == "combobox"


async def test_type_click_submit_flow(client: httpx.AsyncClient, server: str) -> None:
    await post(client, "/nav", url=f"{server}/form")
    snap = (await post(client, "/snapshot")).json()
    q = by_name(snap, "Query")["id"]
    r = await post(client, "/type", element_id=q, text="hello world")
    assert r.status_code == 200
    snap = (await post(client, "/snapshot")).json()
    assert by_name(snap, "Query")["value"] == "hello world"
    r = await post(client, "/click", element_id=by_name(snap, "Search")["id"])
    assert r.json()["url"].endswith("/result?q=hello+world&pw=&color=r")
    assert r.json()["title"] == "Result"
    back = await post(client, "/back")
    assert back.json()["url"].endswith("/form")


async def test_submit_with_enter_and_press(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    snap = (await post(client, "/snapshot")).json()
    r = await post(
        client, "/type", element_id=by_name(snap, "Query")["id"], text="zz", submit=True
    )
    assert "/result?q=zz" in r.json()["url"]
    await post(client, "/nav", url=f"{server}/form")
    snap = (await post(client, "/snapshot")).json()
    await post(client, "/click", element_id=by_name(snap, "Query")["id"])
    await post(client, "/press", key="a")
    snap = (await post(client, "/snapshot")).json()
    assert by_name(snap, "Query")["value"] == "a"


async def test_element_ids_stable_across_snapshots(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    a = (await post(client, "/snapshot")).json()["elements"]
    await post(client, "/scroll", direction="down")
    b = (await post(client, "/snapshot")).json()["elements"]
    assert [(e["id"], e["name"]) for e in a] == [(e["id"], e["name"]) for e in b]
    assert sorted(e["id"] for e in a) == list(range(1, len(a) + 1))


async def test_click_by_selector_select_and_secret_masked(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    snap = (await post(client, "/snapshot")).json()
    await post(
        client, "/type", element_id=by_name(snap, "Secret")["id"], text="hunter2"
    )
    await post(
        client, "/select", element_id=by_name(snap, "Color")["id"], value="Green"
    )
    await post(client, "/click", selector="text=Press me")
    snap = (await post(client, "/snapshot")).json()
    assert "clicked" in snap["text"]
    assert by_name(snap, "Color")["value"] == "Green"
    assert "hunter2" not in str(snap)
    assert by_name(snap, "Secret")["value"] == "(hidden)"


async def test_missing_element_and_validation_errors(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/form")
    r = await post(client, "/click", element_id=9999)
    assert r.status_code == 404
    assert r.json()["error"] == "element_not_found"
    r = await post(client, "/click")
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"
    r = await post(client, "/click", element_id=1, selector="a")
    assert r.status_code == 422
    r = await post(client, "/press", key="x; drop")
    assert r.status_code == 422
    assert (await post(client, "/evaluate", script="1")).status_code == 404


async def test_extract_markdown_and_selector(
    client: httpx.AsyncClient, server: str
) -> None:
    await post(client, "/nav", url=f"{server}/article")
    r = (await post(client, "/extract")).json()
    assert r["tainted"] is True
    assert "Big Story" in r["markdown"]
    assert "footer junk" not in r["markdown"]
    sel = (await post(client, "/extract", goal="h1")).json()
    assert "Big Story" in sel["markdown"]
    assert (await post(client, "/extract", goal="#nope")).status_code == 404


async def test_screenshot_png_base64(client: httpx.AsyncClient, server: str) -> None:
    await post(client, "/nav", url=f"{server}/form")
    r = (await post(client, "/screenshot")).json()
    assert r["mime"] == "image/png"
    assert base64.b64decode(r["data"])[:4] == b"\x89PNG"
    full = (await post(client, "/screenshot", full_page=True)).json()
    assert full["bytes"] > 0


async def test_scroll_reports_position(client: httpx.AsyncClient, server: str) -> None:
    await post(client, "/nav", url=f"{server}/big")
    down = (await post(client, "/scroll", direction="down", amount=500)).json()
    assert down["scroll_y"] == 500
    bottom = (await post(client, "/scroll", direction="bottom")).json()
    assert bottom["scroll_y"] > 500
    top = (await post(client, "/scroll", direction="top")).json()
    assert top["scroll_y"] == 0


async def test_tabs_new_switch_close(client: httpx.AsyncClient, server: str) -> None:
    await post(client, "/nav", url=f"{server}/form")
    t2 = (await post(client, "/tabs/new", url=f"{server}/page2")).json()
    tabs = (await client.get("/tabs")).json()
    assert len(tabs["tabs"]) == 2
    assert tabs["tainted"] is True
    assert tabs["active"] == "t2"
    assert (await post(client, "/snapshot")).json()["title"] == "Second"
    await post(client, "/tabs/switch", tab="t1")
    assert (await post(client, "/snapshot")).json()["title"] == "Fixture Form"
    by_tab = (await post(client, "/snapshot", tab=t2["tab"])).json()
    assert by_tab["title"] == "Second"
    assert (await post(client, "/close", tab="t2")).json()["closed"] is True
    assert (await post(client, "/snapshot")).json()["title"] == "Fixture Form"
    assert (await post(client, "/snapshot", tab="t99")).status_code == 404


async def test_close_session_and_token(make, server: str) -> None:
    c = await make(token="s3cret")
    assert (await post(c, "/nav", url=f"{server}/form")).status_code == 401
    r = await c.post(
        "/nav", json={"url": f"{server}/form"}, headers={"X-Browser-Token": "wrong"}
    )
    assert r.status_code == 401
    assert r.json() == {
        "error": "unauthorized",
        "detail": "bad or missing X-Browser-Token",
    }
    ok = {"X-Browser-Token": "s3cret"}
    r = await c.post("/nav", json={"url": f"{server}/form"}, headers=ok)
    assert r.status_code == 200
    assert (await c.get("/health")).status_code == 200
    r = await c.post("/close", json={}, headers=ok)
    assert r.json() == {"closed": True, "session": True}
