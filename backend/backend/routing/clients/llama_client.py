"""Streaming client for llama-server's OpenAI-compatible /v1/chat/completions."""

import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from backend.core.exceptions import DomainException
from backend.routing.clients.llama_parse import (
    ContentFilter,
    new_call_id,
    parse_arguments,
    parse_tag_call,
)
from backend.routing.clients.llm_types import (
    LLMEvent,
    LLMFinish,
    ParsedToolCall,
    TextDelta,
)

logger = logging.getLogger(__name__)
LLM_UNAVAILABLE = 4000
_THINK = re.compile(r"<think>.*?(</think>|$)", re.DOTALL)


@dataclass(frozen=True)
class Sampling:
    """Sampling and thinking knobs sent with every streamed request."""

    thinking: str = "on"  # on | off | auto (auto = server template default)
    temperature: float | None = 0.6
    top_p: float | None = 0.95
    top_k: int | None = 20
    presence_penalty: float | None = 0.0
    max_tokens: int | None = None

    def apply(self, payload: dict[str, Any]) -> None:
        for key in ("temperature", "top_p", "top_k", "presence_penalty", "max_tokens"):
            if (value := getattr(self, key)) is not None:
                payload[key] = value
        if self.thinking in ("on", "off"):
            payload["chat_template_kwargs"] = {"enable_thinking": self.thinking == "on"}


class LlamaClient:
    def __init__(
        self,
        base_url: str,
        model: str = "dot",
        client: httpx.AsyncClient | None = None,
        sampling: Sampling | None = None,
        debug_file: Path | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._sampling = sampling or Sampling()
        self._debug_file = debug_file
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(600.0, connect=3.0)
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        root = self._base.removesuffix("/v1")
        try:
            r = await self._client.get(f"{root}/health", timeout=3.0)
        except httpx.HTTPError:
            return False
        return r.status_code == httpx.codes.OK

    async def complete(
        self, messages: list[dict[str, Any]], max_tokens: int = 1024
    ) -> str:
        """Non-streaming helper. Reasoning is dropped; raises 4000 on failure."""
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "cache_prompt": True,
        }
        try:
            r = await self._client.post(f"{self._base}/chat/completions", json=payload)
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("llm complete failed: %s", type(exc).__name__)
            raise DomainException(LLM_UNAVAILABLE) from exc
        if r.status_code != httpx.codes.OK or not isinstance(data, dict):
            logger.warning("llm complete http %s", r.status_code)
            raise DomainException(LLM_UNAVAILABLE)
        try:
            text = data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, AttributeError) as exc:
            raise DomainException(LLM_UNAVAILABLE) from exc
        return _THINK.sub("", text).strip()

    async def _lines(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        try:
            async with self._client.stream(
                "POST", f"{self._base}/chat/completions", json=payload
            ) as resp:
                if resp.status_code != httpx.codes.OK:
                    await resp.aread()
                    logger.warning("llm http %s", resp.status_code)
                    raise DomainException(LLM_UNAVAILABLE)
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("llm sent non-JSON sse line")
                        continue
                    if isinstance(chunk, dict) and chunk.get("error"):
                        logger.warning("llm stream error: %s", chunk["error"])
                        raise DomainException(LLM_UNAVAILABLE)
                    yield chunk
        except httpx.HTTPError as exc:
            logger.warning("llm transport error: %s", type(exc).__name__)
            raise DomainException(LLM_UNAVAILABLE) from exc

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "cache_prompt": True,
        }
        if tools:
            payload["tools"] = tools
        self._sampling.apply(payload)
        if self._debug_file:  # capture the exact request body for replay
            with self._debug_file.open("a") as fh:
                fh.write(json.dumps(payload) + "\n")
        flt = ContentFilter()
        acc: dict[int, dict[str, str]] = {}
        finish = LLMFinish()
        async for chunk in self._lines(payload):
            for text, thinking in _consume(chunk, flt, acc, finish):
                yield TextDelta(text, thinking)
        for text, thinking in flt.flush():
            yield TextDelta(text, thinking)
        finish.tool_calls = _assemble(acc) or _from_tags(flt.calls, tools)
        if finish.reason == "length":
            # Output was cut off (context or token limit): never run a cut-off call.
            for call in finish.tool_calls:
                call.error = "output was truncated by the length limit"
        yield finish


def _consume(
    chunk: dict[str, Any],
    flt: ContentFilter,
    acc: dict[int, dict[str, str]],
    finish: LLMFinish,
) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    usage = chunk.get("usage")
    if usage:
        finish.prompt_tokens = usage.get("prompt_tokens")
        finish.completion_tokens = usage.get("completion_tokens")
    for choice in chunk.get("choices") or []:
        delta = choice.get("delta") or {}
        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
        if reasoning:
            out.append((reasoning, True))
        if delta.get("content"):
            out.extend(flt.feed(delta["content"]))
        for tc in delta.get("tool_calls") or []:
            slot = acc.setdefault(
                tc.get("index", 0), {"id": "", "name": "", "args": ""}
            )
            slot["id"] = tc.get("id") or slot["id"]
            fn = tc.get("function") or {}
            slot["name"] += fn.get("name") or ""
            slot["args"] += fn.get("arguments") or ""
        if choice.get("finish_reason"):
            finish.reason = choice["finish_reason"]
    return out


def _assemble(acc: dict[int, dict[str, str]]) -> list[ParsedToolCall]:
    calls = []
    for _, slot in sorted(acc.items()):
        args, err = parse_arguments(slot["args"])
        if not slot["name"]:
            err = err or "tool call without a name"
        calls.append(
            ParsedToolCall(
                slot["id"] or new_call_id(), slot["name"], args, slot["args"], err
            )
        )
    return calls


def _from_tags(bodies: list[str], tools: list[dict[str, Any]]) -> list[ParsedToolCall]:
    """Tag-format calls; param types come from the tool schemas."""
    types = {
        t["function"]["name"]: {
            k: v.get("type", "")
            for k, v in t["function"]["parameters"].get("properties", {}).items()
        }
        for t in tools
    }
    out = []
    for body in bodies:
        call = parse_tag_call(body)
        out.append(parse_tag_call(body, types.get(call.name)) if call.name else call)
    return out
