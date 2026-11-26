from helpers import new_session
from httpx import AsyncClient


async def test_defaults_then_saved(authed: AsyncClient):
    r = await authed.get("/v1/preferences")
    assert r.json() == {"tone": "balanced", "emoji": "less"}
    r = await authed.put("/v1/preferences", json={"tone": "blunt", "emoji": "none"})
    assert r.json() == {"tone": "blunt", "emoji": "none"}
    assert (await authed.get("/v1/preferences")).json()["tone"] == "blunt"


async def test_unknown_value_is_rejected(authed: AsyncClient):
    r = await authed.put("/v1/preferences", json={"tone": "rude", "emoji": "none"})
    assert r.status_code == 422


async def test_style_reaches_the_prompt_and_rebuilds_on_change(
    authed: AsyncClient, app
):
    sid = await new_session(authed)
    tiers = app.state.tiers
    first = await tiers.suffix(sid)
    assert "Emojis: at most one or two" in first.text
    await authed.put("/v1/preferences", json={"tone": "blunt", "emoji": "none"})
    after = await tiers.suffix(sid)
    assert "Emojis: never use them." in after.text
    assert "direct and blunt" in after.text
