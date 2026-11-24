import gzip
from collections.abc import Callable

import httpx
from backend.cognition.services.tools.registry import ToolContext
from backend.cognition.services.tools.web.fetch_http import SafeFetcher
from backend.core.ssrf import Resolver

PUBLIC = "93.184.216.34"
Handler = Callable[[httpx.Request], httpx.Response]


def ctx(session: str = "S1") -> ToolContext:
    return ToolContext(session_id=session, sandbox=None, workspace="/w")  # type: ignore[arg-type]


def fixed(*ips: str) -> Resolver:
    async def resolve(_host: str, _port: int) -> list[str]:
        return list(ips)

    return resolve


def counting(*ips: str) -> tuple[Resolver, list[str]]:
    seen: list[str] = []

    async def resolve(host: str, _port: int) -> list[str]:
        seen.append(host)
        return list(ips)

    return resolve, seen


class _Chunks(httpx.AsyncByteStream):
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aiter__(self):
        for i in range(0, len(self._data), 65536):
            yield self._data[i : i + 65536]


class HandlerTransport(httpx.AsyncBaseTransport):
    """Like MockTransport but leaves the body streamable (aiter_raw)."""

    def __init__(self, handler: Handler) -> None:
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        r = self._handler(request)
        return httpx.Response(
            r.status_code,
            headers=r.headers,
            stream=_Chunks(b"".join(r.stream)),  # type: ignore[arg-type]
            request=request,
        )


def fetcher(handler: Handler, resolver: Resolver | None = None, **kw) -> SafeFetcher:
    return SafeFetcher(
        resolver=resolver or fixed(PUBLIC), transport=HandlerTransport(handler), **kw
    )


def html_page(body: str, title: str = "T") -> httpx.Response:
    html = f"<html><head><title>{title}</title></head><body>{body}</body></html>"
    return httpx.Response(200, text=html, headers={"content-type": "text/html"})


def gz(data: bytes) -> bytes:
    return gzip.compress(data)
