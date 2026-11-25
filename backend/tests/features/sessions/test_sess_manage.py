from backend.routing.clients.scripted import ScriptedLLM, reply
from httpx import AsyncClient
from sess_helpers import chat, make, rows


async def test_new_session_has_the_v2_fields(authed: AsyncClient):
    sid = await make(authed)
    body = (await authed.get("/v1/sessions")).json()[0]
    assert body["id"] == sid
    assert body["pinned"] is False
    assert body["archived"] is False
    assert body["effort"] == "medium"
    assert body["state"] == "idle"
    assert body["message_count"] == 0
    assert body["parent_id"] is None


async def test_patch_title_pin_archive_effort_project(authed: AsyncClient):
    sid = await make(authed)
    r = await authed.patch(
        f"/v1/sessions/{sid}",
        json={"title": "  My  plan ", "pinned": True, "effort": "max", "project": "p1"},
    )
    body = r.json()
    assert body["title"] == "My plan"
    assert body["pinned"] is True
    assert body["effort"] == "max"
    assert body["project"] == "p1"
    r = await authed.patch(f"/v1/sessions/{sid}", json={"project": ""})
    assert r.json()["project"] is None
    # archived rows are hidden unless asked for
    await authed.patch(f"/v1/sessions/{sid}", json={"archived": True})
    assert (await authed.get("/v1/sessions")).json() == []
    shown = (await authed.get("/v1/sessions?archived=true")).json()
    assert [s["id"] for s in shown] == [sid]


async def test_patch_rejects_a_bad_effort_and_unknown_session(authed: AsyncClient):
    sid = await make(authed)
    assert (
        await authed.patch(f"/v1/sessions/{sid}", json={"effort": "ultra"})
    ).status_code == 422
    r = await authed.patch("/v1/sessions/Sxxxxxxxxx", json={"title": "x"})
    assert r.status_code == 404


async def test_list_filters_and_cursor(authed: AsyncClient):
    ids = [await make(authed) for _ in range(3)]
    await authed.patch(f"/v1/sessions/{ids[0]}", json={"pinned": True})
    pinned = (await authed.get("/v1/sessions?pinned=true")).json()
    assert [s["id"] for s in pinned] == [ids[0]]
    page1 = (await authed.get("/v1/sessions?limit=2")).json()
    assert len(page1) == 2
    page2 = (await authed.get(f"/v1/sessions?limit=2&before={page1[-1]['id']}")).json()
    assert len(page2) == 1
    assert {s["id"] for s in page1 + page2} == set(ids)


async def test_activity_count_and_last_message(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply("hello")]
    sid = await make(authed)
    await chat(authed, sid, "hi")
    info = (await authed.get("/v1/sessions")).json()[0]
    assert info["message_count"] == 2
    assert info["last_message_at"].endswith("Z")


async def test_delete_needs_confirm_and_removes_everything(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("zebra answer")]
    sid = await make(authed)
    await chat(authed, sid, "zebra question")
    r = await authed.delete(f"/v1/sessions/{sid}")
    assert r.status_code == 400
    assert (await authed.delete(f"/v1/sessions/{sid}?confirm=nope")).status_code == 400
    assert (await authed.delete(f"/v1/sessions/{sid}?confirm={sid}")).json() == {
        "ok": True
    }
    assert (await authed.get("/v1/sessions")).json() == []
    assert (await authed.get(f"/v1/sessions/{sid}/messages")).status_code == 404
    # FTS rows are gone too
    other = await make(authed)
    assert other
    assert (await authed.get("/v1/sessions?q=zebra")).json() == []


async def test_state_follows_the_running_turn(authed: AsyncClient, app, llm):
    import asyncio  # noqa: PLC0415

    gate = asyncio.Event()
    llm.scripts = [[gate, *reply("done")]]
    sid = await make(authed)
    task = asyncio.create_task(
        authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})
    )
    for _ in range(200):
        if app.state.turns.is_active(sid):
            break
        await asyncio.sleep(0.01)
    assert (await authed.get("/v1/sessions")).json()[0]["state"] == "running"
    assert (await authed.delete(f"/v1/sessions/{sid}?confirm={sid}")).status_code == 409
    gate.set()
    await task
    assert (await authed.get("/v1/sessions")).json()[0]["state"] == "idle"
    assert len(await rows(authed, sid)) == 2
