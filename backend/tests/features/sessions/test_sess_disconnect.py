import asyncio

from backend.cognition.services.engine.chat_stream import _drain
from backend.routing.clients.llm_types import LLMFinish, TextDelta
from backend.routing.clients.scripted import ScriptedLLM
from dot_contracts.events import DoneEvent, TokenEvent
from helpers import new_session
from httpx import AsyncClient
from sess_helpers import rows


async def test_a_reader_leaving_does_not_kill_the_turn():
    queue: asyncio.Queue = asyncio.Queue()
    gate = asyncio.Event()

    async def turn() -> None:
        await queue.put(TokenEvent(text="a"))
        await gate.wait()  # still running when the reader leaves
        await queue.put(DoneEvent(stop_reason="end_turn"))
        await queue.put(None)

    task = asyncio.create_task(turn())
    stream = _drain(queue, task)
    assert "token" in await anext(stream)
    await stream.aclose()  # tab closed / web restarted
    gate.set()
    await asyncio.wait_for(task, 2)
    assert not task.cancelled()


async def test_stop_mid_answer_keeps_what_was_written(
    authed: AsyncClient, llm: ScriptedLLM
):
    gate = asyncio.Event()
    llm.scripts = [[TextDelta("Half an answer"), gate, LLMFinish()]]
    sid = await new_session(authed)
    chat = asyncio.create_task(
        authed.post(f"/v1/sessions/{sid}/chat", json={"message": "q"})
    )
    async with asyncio.timeout(5):
        while not llm.requests:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)
    assert (await authed.post(f"/v1/sessions/{sid}/stop")).json()["stopped"]
    await chat
    texts = [m["content"] for m in await rows(authed, sid)]
    assert texts == ["q", "Half an answer\n\n(stopped)"]
