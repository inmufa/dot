"""Fake llama-server: OpenAI chat-completions SSE in the real llama.cpp chunk shapes.

Shapes follow tools/server/server-task.cpp (to_json_oaicompat_chat_stream): a role
chunk, reasoning_content / content deltas, tool_calls deltas (id+name first, then
argument fragments), one finish_reason chunk with an empty delta, then a usage chunk
with `choices: []` and `timings`, then `data: [DONE]`.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route


@dataclass
class Turn:
    reasoning: str = ""
    content: str = ""
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    finish: str | None = None  # default: tool_calls if calls else stop
    error_after: bool = False  # emit a mid-stream error chunk instead of finishing


@dataclass
class FakeLlama:
    script: list[Turn] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)

    def reset(self, script: list[Turn]) -> None:
        self.script = list(script)
        self.requests.clear()

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                Route("/health", self._health),
                Route("/v1/chat/completions", self._chat, methods=["POST"]),
            ]
        )

    async def _health(self, _: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def _chat(self, request: Request) -> Response:
        body = await request.json()
        self.requests.append(body)
        turn = self.script.pop(0) if self.script else Turn(content="(script empty)")
        if not body.get("stream"):
            msg = {"role": "assistant", "content": turn.content or "summary"}
            return JSONResponse({"choices": [{"message": msg}]})
        return StreamingResponse(
            _sse(turn, len(self.requests)), media_type="text/event-stream"
        )


def _chunk(delta: dict[str, Any], finish: str | None, cid: str) -> dict[str, Any]:
    return {
        "choices": [{"finish_reason": finish, "index": 0, "delta": delta}],
        "created": 1,
        "id": cid,
        "model": "fake",
        "object": "chat.completion.chunk",
    }


def _split(text: str, parts: int = 3) -> list[str]:
    size = max(1, -(-len(text) // parts))
    return [text[i : i + size] for i in range(0, len(text), size)]


def _frames(turn: Turn, cid: str) -> list[dict[str, Any]]:
    out = [_chunk({"role": "assistant", "content": None}, None, cid)]
    out += (
        [_chunk({"reasoning_content": t}, None, cid) for t in _split(turn.reasoning)]
        if turn.reasoning
        else []
    )
    out += (
        [_chunk({"content": t}, None, cid) for t in _split(turn.content)]
        if turn.content
        else []
    )
    for index, (name, args) in enumerate(turn.calls):
        head = {"index": index, "id": f"call_{cid}_{index}", "type": "function"}
        first = {**head, "function": {"name": name, "arguments": ""}}
        out.append(_chunk({"tool_calls": [first]}, None, cid))
        for frag in _split(json.dumps(args)):
            delta = {"tool_calls": [{"index": index, "function": {"arguments": frag}}]}
            out.append(_chunk(delta, None, cid))
    return out


async def _sse(turn: Turn, n: int) -> AsyncIterator[str]:
    cid = f"chatcmpl-{n}"
    for frame in _frames(turn, cid):
        yield f"data: {json.dumps(frame)}\n\n"
    if turn.error_after:
        err = {"error": {"code": 500, "message": "boom", "type": "server_error"}}
        yield f"data: {json.dumps(err)}\n\n"
        return
    finish = turn.finish or ("tool_calls" if turn.calls else "stop")
    yield f"data: {json.dumps(_chunk({}, finish, cid))}\n\n"
    usage = {"prompt_tokens": 120 + n, "completion_tokens": 12, "total_tokens": 132 + n}
    last = {
        "choices": [],
        "created": 1,
        "id": cid,
        "model": "fake",
        "object": "chat.completion.chunk",
        "usage": usage,
        "timings": {"prompt_n": 120, "prompt_ms": 50.0, "predicted_n": 12},
    }
    yield f"data: {json.dumps(last)}\n\n"
    yield "data: [DONE]\n\n"
