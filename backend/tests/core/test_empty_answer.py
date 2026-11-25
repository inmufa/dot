"""Empty visible answer after thinking: one nudge, then promote the reasoning."""

import json

import httpx
from backend.cognition.services.engine.history import to_chat_messages
from backend.cognition.services.engine.react_engine import _EMPTY_NUDGE, _promote
from backend.routing.clients.llama_client import LlamaClient, Sampling
from backend.routing.clients.scripted import ScriptedLLM, reply
from backend.sessions.models import Message
from helpers import new_session, parse_sse, start_chat
from httpx import AsyncClient


async def run(c: AsyncClient, sid: str):
    resp = await start_chat(c, sid, "say hi")
    return parse_sse(resp.text), (await c.get(f"/v1/sessions/{sid}/messages")).json()


async def test_empty_reply_gets_one_nudge_then_answers(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [
        reply(thinking="the answer is hi"),
        reply("hi", thinking="ok"),
    ]
    ev, msgs = await run(authed, await new_session(authed))
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert len(llm.requests) == 2
    sent = llm.requests[1]["messages"]
    assert sent[-1] == {"role": "user", "content": _EMPTY_NUDGE}
    assert sent[-2] == {
        "role": "assistant",
        "content": "",
        "reasoning_content": "the answer is hi",
    }
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[-1]["content"] == "hi"
    assert "reasoning_promoted" not in msgs[-1]["meta"]


async def test_nudge_keeps_history_append_only(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply(thinking="t"), reply("done")]
    await run(authed, await new_session(authed))
    first, second = (r["messages"] for r in llm.requests)
    assert second[: len(first)] == first  # same prefix, only appended rows


async def test_still_empty_promotes_reasoning(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply(thinking="draft"), reply(thinking="plan\n\nThe answer is hi.")]
    ev, msgs = await run(authed, await new_session(authed))
    assert len(llm.requests) == 2  # retried exactly once
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    visible = [e["text"] for e in ev if e["type"] == "token" and not e["thinking"]]
    assert visible == ["plan\n\nThe answer is hi."]
    assert msgs[-1]["content"] == "plan\n\nThe answer is hi."
    assert msgs[-1]["meta"]["reasoning_promoted"] is True


async def test_empty_without_any_reasoning_ends_quietly(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply(), reply()]
    ev, msgs = await run(authed, await new_session(authed))
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert msgs[-1]["content"] == ""


async def test_tool_call_without_text_is_not_empty(
    authed: AsyncClient, llm: ScriptedLLM, ws
):
    llm.scripts = [
        reply(calls=[("Glob", {"pattern": "*.py"})], thinking="look"),
        reply("found"),
    ]
    await run(authed, await new_session(authed))
    assert len(llm.requests) == 2
    assert all(
        m.get("content") != _EMPTY_NUDGE for r in llm.requests for m in r["messages"]
    )


def test_promote_keeps_last_paragraphs_within_cap():
    text = "\n\n".join(f"para {i} " + "x" * 300 for i in range(10))
    out = _promote(text)
    assert out.endswith("x" * 300)
    assert "para 9" in out
    assert "para 0" not in out
    assert len(out) <= 1200


def test_history_replays_reasoning_on_assistant_rows():
    rows = [
        Message(seq=1, role="user", content="go"),
        Message(
            seq=2,
            role="assistant",
            content="",
            reasoning="run echo",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "Bash"}}],
        ),
        Message(seq=3, role="assistant", content="plain"),
    ]
    msgs = to_chat_messages("sys", rows)
    assert msgs[2]["reasoning_content"] == "run echo"
    assert "reasoning_content" not in msgs[3]


async def test_client_sends_sampling_and_thinking_flag(tmp_path):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, text="data: [DONE]\n\n")

    debug = tmp_path / "req.jsonl"
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    for thinking in ("on", "off", "auto"):
        client = LlamaClient(
            "http://x/v1",
            client=http,
            sampling=Sampling(thinking=thinking, temperature=0.5, top_k=7),
            debug_file=debug,
        )
        async for _ in client.stream([{"role": "user", "content": "hi"}], []):
            pass
    assert seen[0]["chat_template_kwargs"] == {"enable_thinking": True}
    assert seen[1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "chat_template_kwargs" not in seen[2]
    assert seen[0]["temperature"] == 0.5
    assert seen[0]["top_k"] == 7
    assert "max_tokens" not in seen[0]
    assert len(debug.read_text().splitlines()) == 3
