import json

import httpx
import pytest
from backend.core.exceptions import DomainException
from backend.routing.clients.llama_client import LlamaClient
from backend.routing.clients.llama_parse import (
    ContentFilter,
    parse_arguments,
    parse_tag_call,
)
from backend.routing.clients.llm_types import LLMFinish, TextDelta


def feed_all(chunks: list[str]) -> tuple[list[tuple[str, bool]], list[str]]:
    flt = ContentFilter()
    out: list[tuple[str, bool]] = []
    for c in chunks:
        out += flt.feed(c)
    out += flt.flush()
    return out, flt.calls


def test_filter_splits_think_across_chunks():
    out, _ = feed_all(["<thi", "nk>plan it</th", "ink>answer"])
    assert "".join(t for t, th in out if th) == "plan it"
    assert "".join(t for t, th in out if not th) == "answer"


def test_filter_plain_less_than_is_text():
    out, calls = feed_all(["a < b and <", "b>"])
    assert "".join(t for t, _ in out) == "a < b and <b>"
    assert calls == []


def test_filter_collects_tool_call_body():
    out, calls = feed_all(
        ['hi <tool_call>{"name":"Read",', '"arguments":{}}</tool_call>']
    )
    assert "".join(t for t, _ in out) == "hi "
    assert len(calls) == 1


def test_parse_arguments_repairs_truncated_json():
    assert parse_arguments('{"file_path": "/a"') == ({"file_path": "/a"}, None)
    assert parse_arguments('{"file_path": "/a')[1] is not None  # cut mid-string
    assert parse_arguments("")[0] == {}
    assert parse_arguments("[1]")[1] is not None
    assert parse_arguments("{nope")[1] is not None


def test_tag_call_json_and_xml():
    c = parse_tag_call('{"name": "Read", "arguments": {"file_path": "/x"}}')
    assert c
    assert c.name == "Read"
    assert c.arguments == {"file_path": "/x"}
    xml = (
        "<function=Edit>\n<parameter=file_path>\n/x\n</parameter>\n"
        "<parameter=replace_all>\ntrue\n</parameter>\n</function>"
    )
    c = parse_tag_call(xml, {"replace_all": "boolean"})
    assert c
    assert c.name == "Edit"
    assert c.arguments == {"file_path": "/x", "replace_all": True}


def _sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]
    return "".join(lines).encode()


def _client(body: bytes, status: int = 200) -> LlamaClient:
    transport = httpx.MockTransport(lambda _r: httpx.Response(status, content=body))
    return LlamaClient("http://llm/v1", client=httpx.AsyncClient(transport=transport))


async def collect(client: LlamaClient):
    return [e async for e in client.stream([], [])]


async def test_stream_text_reasoning_and_split_tool_call():
    body = _sse(
        {"choices": [{"delta": {"reasoning_content": "hmm"}}]},
        {"choices": [{"delta": {"content": "ok"}}]},
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c1",
                                "function": {"name": "Read", "arguments": '{"file_'},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": 'path": "/a"}'}}
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {"choices": [], "usage": {"prompt_tokens": 42, "completion_tokens": 7}},
    )
    events = await collect(_client(body))
    assert events[0] == TextDelta("hmm", thinking=True)
    assert events[1] == TextDelta("ok")
    fin = events[-1]
    assert isinstance(fin, LLMFinish)
    assert fin.reason == "tool_calls"
    assert fin.prompt_tokens == 42
    assert fin.tool_calls[0].id == "c1"
    assert fin.tool_calls[0].arguments == {"file_path": "/a"}


async def test_stream_falls_back_to_tool_call_tags_in_content():
    text = 'sure<tool_call>{"name":"Bash","arguments":{"command":"ls"}}</tool_call>'
    body = _sse({"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]})
    events = await collect(_client(body))
    assert events[0] == TextDelta("sure")
    fin = events[-1]
    assert isinstance(fin, LLMFinish)
    assert fin.tool_calls[0].name == "Bash"
    assert fin.tool_calls[0].arguments == {"command": "ls"}


async def test_stream_marks_broken_arguments():
    body = _sse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c",
                                "function": {"name": "Read", "arguments": "{{{"},
                            }
                        ]
                    }
                }
            ]
        }
    )
    fin = (await collect(_client(body)))[-1]
    assert isinstance(fin, LLMFinish)
    assert fin.tool_calls[0].error


async def test_http_error_is_domain_4000():
    with pytest.raises(DomainException) as exc:
        await collect(_client(b"boom", status=500))
    assert exc.value.code == 4000
