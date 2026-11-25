import httpx
from backend.routing.clients.llama_client import LlamaClient


def _client(handler) -> LlamaClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LlamaClient("http://llm/v1", client=http)


async def test_levels_read_from_props():
    def h(_req):
        caps = {"chat_template_caps": {"reasoning_effort_levels": ["low", "high"]}}
        return httpx.Response(200, json=caps)

    assert await _client(h).reasoning_levels() == ["low", "high"]


async def test_probe_failures_are_empty():
    assert await _client(lambda _r: httpx.Response(404)).reasoning_levels() == []
    assert (
        await _client(lambda _r: httpx.Response(200, text="x")).reasoning_levels() == []
    )

    def boom(_req):
        msg = "down"
        raise httpx.ConnectError(msg)

    assert await _client(boom).reasoning_levels() == []
