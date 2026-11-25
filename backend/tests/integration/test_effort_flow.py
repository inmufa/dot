"""Effort over real HTTP: the request body that reaches llama-server."""

import json

import httpx
import pytest
from drive import AUTH, new_session
from fake_llama import FakeLlama, Turn

pytestmark = pytest.mark.integration


def _chat(base: str, sid: str, **body) -> list[dict]:
    r = httpx.post(
        f"{base}/v1/sessions/{sid}/chat", json=body, headers=AUTH, timeout=40.0
    )
    assert r.status_code == httpx.codes.OK, r.text
    return [json.loads(x[6:]) for x in r.text.split("\n\n") if x.startswith("data: ")]


def test_effort_reaches_llama_body(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(content="a"), Turn(content="b"), Turn(content="c")])
    sid = new_session(backend_url)
    _chat(backend_url, sid, message="hi", effort="off")
    off = fake.requests[0]
    assert off["chat_template_kwargs"] == {"enable_thinking": False}
    assert off["max_tokens"] == 2048
    assert "reasoning_effort" not in off
    _chat(backend_url, sid, message="hi", effort="high")
    high = fake.requests[1]
    assert high["chat_template_kwargs"] == {"enable_thinking": True}
    assert high["max_tokens"] == 12000
    ev = _chat(backend_url, sid, message="hi")
    assert "max_tokens" not in fake.requests[2]  # medium: client default
    usage = next(e for e in ev if e["type"] == "usage")
    assert usage["effort"]["level"] == "medium"
    assert usage["prompt_tokens"] > 0
