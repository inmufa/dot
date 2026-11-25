import pytest
from backend.routing.clients.scripted import ScriptedLLM, reply
from backend.sessions.services.search.fts import match_query
from httpx import AsyncClient
from sess_helpers import chat, make


async def test_search_finds_title_and_message_text(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("the capybara is a rodent"), reply("nothing here")]
    a = await make(authed)
    b = await make(authed)
    await chat(authed, a, "tell me about animals")
    await chat(authed, b, "quokka facts please")
    hit = (await authed.get("/v1/sessions?q=capybara")).json()
    assert [s["id"] for s in hit] == [a]
    assert "capybara" in hit[0]["snippet"]
    title = (await authed.get("/v1/sessions?q=quokk")).json()  # prefix on the title
    assert [s["id"] for s in title] == [b]


async def test_search_follows_a_rename(authed: AsyncClient):
    sid = await make(authed)
    await authed.patch(f"/v1/sessions/{sid}", json={"title": "gazpacho notes"})
    assert [s["id"] for s in (await authed.get("/v1/sessions?q=gazpacho")).json()] == [
        sid
    ]
    await authed.patch(f"/v1/sessions/{sid}", json={"title": "borscht"})
    assert (await authed.get("/v1/sessions?q=gazpacho")).json() == []


@pytest.mark.parametrize(
    "q",
    [
        '"',
        "'",
        "AND OR NOT",
        "a*",
        "(",
        ")",
        "NEAR(",
        "col:x",
        "-",
        '" OR 1=1 --',
        "\\",
        "%",
        ";",
    ],
)
async def test_hostile_search_strings_never_error(authed: AsyncClient, q: str):
    await make(authed)
    r = await authed.get("/v1/sessions", params={"q": q})
    assert r.status_code == 200


async def test_empty_query_lists_everything(authed: AsyncClient):
    await make(authed)
    assert len((await authed.get("/v1/sessions?q=")).json()) == 1
    assert len((await authed.get("/v1/sessions?q=%20%20")).json()) == 1


def test_match_query_is_inert():
    assert match_query("") is None
    assert match_query('" OR x') == '"OR"* "x"*'
    assert match_query("a" * 5 + " b") == '"aaaaa"* "b"*'


async def test_rebuild_indexes_existing_rows_once(authed: AsyncClient, app, llm):
    from backend.sessions.services.search import fts  # noqa: PLC0415
    from sqlalchemy import text  # noqa: PLC0415

    llm.scripts = [reply("walrus tusks")]
    sid = await make(authed)
    await chat(authed, sid, "hello")
    async with app.state.sessions() as db:
        await db.execute(text("DELETE FROM session_fts"))
        await db.commit()
    assert (await authed.get("/v1/sessions?q=walrus")).json() == []
    await fts.rebuild_if_empty(app.state.sessions)
    await fts.rebuild_if_empty(app.state.sessions)  # idempotent
    assert [s["id"] for s in (await authed.get("/v1/sessions?q=walrus")).json()] == [
        sid
    ]
