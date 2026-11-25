import io

import httpx
from backend.cognition.services.engine.images import downscale
from backend.routing.clients.llama_client import LlamaClient
from backend.routing.clients.scripted import reply
from backend.routing.services.telemetry import props_vision
from helpers import new_session
from PIL import Image


def _png(color: str = "white", size: tuple[int, int] = (2000, 1000)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


async def _upload(c, sid: str, name: str, data: bytes) -> str:
    r = await c.post(
        f"/v1/sessions/{sid}/attachments", files=[("files", (name, data, "image/png"))]
    )
    assert r.status_code == 201, r.text
    return r.json()[0]["id"]


async def _chat(c, sid: str, msg: str, att: list[str] | None = None) -> None:
    r = await c.post(
        f"/v1/sessions/{sid}/chat", json={"message": msg, "attachments": att or []}
    )
    assert r.status_code == 200, r.text


def _parts(msg: dict) -> list[str]:
    c = msg["content"]
    return [p["type"] for p in c] if isinstance(c, list) else []


def _text(msg: dict) -> str:
    c = msg["content"]
    return c if isinstance(c, str) else c[0]["text"]


def test_downscale_fits_longest_side_and_keeps_png_alpha():
    out, mime = downscale(_png(), 768)  # type: ignore[misc]
    img = Image.open(io.BytesIO(out))
    assert max(img.size) == 768
    assert mime == "image/jpeg"
    buf = io.BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(buf, "PNG")
    assert downscale(buf.getvalue(), 768)[1] == "image/png"  # type: ignore[index]
    assert downscale(b"not an image", 768) is None


def test_props_vision_reads_modalities():
    assert props_vision({"modalities": {"vision": True}}) is True
    assert props_vision({"modalities": {"vision": False}}) is False
    assert props_vision({}) is False


async def test_llama_client_vision_follows_props():
    state = {"vision": True}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"modalities": {"vision": state["vision"]}})

    client = LlamaClient(
        "http://x/v1", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    assert await client.vision() is True
    state["vision"] = False
    assert await client.vision() is True  # cached
    client._vision_until = 0
    assert await client.vision() is False


async def test_image_attachment_becomes_image_part_when_vision_on(authed, llm):
    llm.has_vision = True
    llm.scripts = [reply("a"), reply("b")]
    sid = await new_session(authed)
    aid = await _upload(authed, sid, "a.png", _png())
    await _chat(authed, sid, "look", [aid])
    first = llm.requests[0]["messages"][-1]
    assert _parts(first) == ["text", "image_url"]
    assert "shown to you below" in _text(first)
    assert first["content"][1]["image_url"]["url"].startswith("data:image/")
    await _chat(authed, sid, "again")
    # prefix byte-stable: the image message is replayed unchanged
    assert (
        llm.requests[1]["messages"][: len(llm.requests[0]["messages"])]
        == (llm.requests[0]["messages"])
    )


async def test_only_last_two_images_stay_full(authed, llm):
    llm.has_vision = True
    llm.scripts = [reply("1"), reply("2"), reply("3")]
    sid = await new_session(authed)
    for i, color in enumerate(("red", "green", "blue")):
        aid = await _upload(authed, sid, f"p{i}.png", _png(color, (64, 64)))
        await _chat(authed, sid, f"m{i}", [aid])
    users = [m for m in llm.requests[2]["messages"] if m["role"] == "user"]
    assert [bool(_parts(m)) for m in users] == [False, True, True]
    assert "[image: p0.png]" in _text(users[0])


async def test_vision_off_tells_the_model_it_cannot_see(authed, llm):
    llm.scripts = [reply("ok")]
    sid = await new_session(authed)
    aid = await _upload(authed, sid, "a.png", _png("white", (64, 64)))
    await _chat(authed, sid, "look", [aid])
    msg = llm.requests[0]["messages"][-1]
    assert _parts(msg) == []
    assert "you cannot see it" in msg["content"]


async def test_read_returns_image_as_follow_up_user_message(authed, llm):
    llm.has_vision = True
    sid = await new_session(authed)
    aid = await _upload(authed, sid, "a.png", _png("white", (64, 64)))
    path = (await authed.get(f"/v1/sessions/{sid}/attachments")).json()[0]["path"]
    llm.scripts = [reply(calls=[("Read", {"file_path": path})]), reply("seen")]
    await _chat(authed, sid, "read it")
    msgs = llm.requests[1]["messages"]
    assert aid
    tool = next(m for m in msgs if m["role"] == "tool")
    assert "[image: " in tool["content"]
    after = msgs[msgs.index(tool) + 1]
    assert after["role"] == "user"
    assert _parts(after) == ["text", "image_url"]


async def test_read_image_without_vision_is_an_error(authed, llm):
    sid = await new_session(authed)
    await _upload(authed, sid, "a.png", _png("white", (64, 64)))
    path = (await authed.get(f"/v1/sessions/{sid}/attachments")).json()[0]["path"]
    llm.scripts = [reply(calls=[("Read", {"file_path": path})]), reply("sorry")]
    await _chat(authed, sid, "read it")
    tool = next(m for m in llm.requests[1]["messages"] if m["role"] == "tool")
    assert "no vision" in tool["content"]
