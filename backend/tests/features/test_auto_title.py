import asyncio
from datetime import timedelta

from backend.routing.clients.scripted import ScriptedLLM, reply
from backend.sessions.services.session_admin import SessionAdmin
from backend.sessions.services.session_service import SessionService
from helpers import new_session, parse_sse
from httpx import AsyncClient


async def chat(c: AsyncClient, sid: str, msg: str):
    r = await c.post(f"/v1/sessions/{sid}/chat", json={"message": msg})
    return parse_sse(r.text)


async def title_of(app, sid: str) -> str | None:
    return (await SessionService(app.state.sessions).get(sid)).title


async def wait_for(app, sid: str, want: str) -> bool:
    for _ in range(40):
        if await title_of(app, sid) == want:
            return True
        await asyncio.sleep(0.05)
    return False


async def test_title_comes_from_model_after_first_exchange(
    authed, llm: ScriptedLLM, app
):
    app.state.settings.auto_title = True
    llm.scripts = [reply("a"), reply("b")]
    llm.completions = ['"Narwhal habitats."']
    sid = await new_session(authed)
    await chat(authed, sid, "where do narwhals live")
    assert await wait_for(app, sid, "Narwhal habitats")
    await chat(authed, sid, "and what do they eat")
    assert len(llm.complete_requests) == 1  # only once


async def test_manual_rename_is_kept(authed, llm: ScriptedLLM, app):
    app.state.settings.auto_title = True
    llm.scripts = [reply("a"), reply("b")]
    llm.completions = ["Should not apply"]
    sid = await new_session(authed)
    r = await authed.patch(f"/v1/sessions/{sid}", json={"title": "My name"})
    assert r.status_code == 200
    await chat(authed, sid, "first")
    await asyncio.sleep(0.3)
    assert await title_of(app, sid) == "My name"
    assert llm.complete_requests == []


async def test_empty_chats_are_purged_but_used_ones_stay(authed, app):
    empty = await new_session(authed)
    used = await new_session(authed)
    await authed.patch(f"/v1/sessions/{used}", json={"title": "kept"})
    admin = SessionAdmin(app.state.sessions)
    assert await admin.purge_empty(timedelta(hours=1)) == 0  # too new
    assert await admin.purge_empty(timedelta(seconds=-1)) == 1
    svc = SessionService(app.state.sessions)
    assert (await svc.get(used)).title == "kept"
    ids = [x["id"] for x in (await authed.get("/v1/sessions")).json()]
    assert empty not in ids
