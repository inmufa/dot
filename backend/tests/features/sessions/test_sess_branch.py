from backend.routing.clients.scripted import ScriptedLLM, reply
from httpx import AsyncClient
from sess_helpers import chat, make, rows


def _tool_turn(text: str) -> list:
    return [reply("", [("Glob", {"pattern": "*.nothing"})]), reply(text)]


async def _two_turns(c: AsyncClient, llm: ScriptedLLM) -> str:
    llm.scripts = [*_tool_turn("answer one"), reply("answer two")]
    sid = await make(c)
    await chat(c, sid, "first")
    await chat(c, sid, "second")
    return sid


async def test_branch_copies_whole_turns_and_links_parent(
    authed: AsyncClient, llm: ScriptedLLM
):
    sid = await _two_turns(authed, llm)
    msgs = await rows(authed, sid)
    second_user = next(m["seq"] for m in msgs if m["content"] == "second")
    r = await authed.post(f"/v1/sessions/{sid}/branch", json={"from_seq": second_user})
    body = r.json()
    new = body["session"]
    assert r.status_code == 200
    assert new["parent_id"] == sid
    assert new["parent_seq"] == body["parent_seq"] == second_user - 1
    copied = await rows(authed, new["id"])
    assert [m["role"] for m in copied] == ["user", "assistant", "tool", "assistant"]
    assert copied[-1]["content"] == "answer one"
    # tool_call / tool pairing intact
    call_id = copied[1]["tool_calls"][0]["id"]
    assert copied[2]["tool_call_id"] == call_id
    # the source is untouched and the branch continues independently
    assert len(await rows(authed, sid)) == len(msgs)
    llm.scripts = [reply("branch answer")]
    ev = await chat(authed, new["id"], "different second")
    assert ev[-1]["stop_reason"] == "end_turn"
    assert len(await rows(authed, sid)) == len(msgs)


async def test_branch_cuts_back_to_a_turn_boundary(
    authed: AsyncClient, llm: ScriptedLLM
):
    sid = await _two_turns(authed, llm)
    msgs = await rows(authed, sid)
    mid_tool = next(m["seq"] for m in msgs if m["role"] == "tool")
    body = (
        await authed.post(f"/v1/sessions/{sid}/branch", json={"from_seq": mid_tool})
    ).json()
    assert body["parent_seq"] == 0  # only the first user row + open call: nothing whole
    assert await rows(authed, body["session"]["id"]) == []


async def test_branch_at_the_end_copies_everything(
    authed: AsyncClient, llm: ScriptedLLM
):
    sid = await _two_turns(authed, llm)
    msgs = await rows(authed, sid)
    r = await authed.post(
        f"/v1/sessions/{sid}/branch", json={"from_seq": msgs[-1]["seq"] + 1}
    )
    assert len(await rows(authed, r.json()["session"]["id"])) == len(msgs)


async def test_branch_validates_from_seq(authed: AsyncClient, llm: ScriptedLLM):
    sid = await _two_turns(authed, llm)
    for bad in (0, -1, 999):
        r = await authed.post(f"/v1/sessions/{sid}/branch", json={"from_seq": bad})
        assert r.status_code in (400, 422)
    r = await authed.post(f"/v1/sessions/{sid}/branch", json={"from_seq": 999})
    assert r.json()[0]["code"] == 2031


async def test_branch_is_searchable_and_inherits_title(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("pangolin facts")]
    sid = await make(authed)
    await chat(authed, sid, "hello there")
    last = (await rows(authed, sid))[-1]["seq"]
    new = (
        await authed.post(f"/v1/sessions/{sid}/branch", json={"from_seq": last + 1})
    ).json()["session"]
    hits = (await authed.get("/v1/sessions?q=pangolin")).json()
    assert {h["id"] for h in hits} == {sid, new["id"]}
    assert new["title"] == "hello there"


async def test_clear_makes_a_new_empty_session(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply("a")]
    sid = await make(authed)
    await chat(authed, sid, "hi")
    await authed.patch(f"/v1/sessions/{sid}", json={"project": "p", "effort": "high"})
    r = await authed.post(f"/v1/sessions/{sid}/clear")
    new = r.json()
    assert r.status_code == 201
    assert new["id"] != sid
    assert new["project"] == "p"
    assert new["effort"] == "high"
    assert new["message_count"] == 0
    assert len(await rows(authed, sid)) == 2
