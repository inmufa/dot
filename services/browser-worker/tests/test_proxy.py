import asyncio

import pytest
from dot_browser.guard import UrlGuard
from dot_browser.proxy import EgressProxy, split_hostport
from dot_browser.settings import Settings


async def ask(port: int, raw: bytes) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(raw)
    await writer.drain()
    data = await asyncio.wait_for(reader.read(4096), 5)
    writer.close()
    return data


@pytest.fixture
async def proxy():
    cfg = Settings()
    guard = UrlGuard(cfg)
    p = EgressProxy(guard, cfg)
    await p.start()
    yield p, guard
    await p.stop()


@pytest.mark.parametrize(
    "host", ["10.0.0.1:443", "169.254.169.254:80", "[::1]:443", "localhost:80"]
)
async def test_connect_to_private_refused(proxy, host: str) -> None:
    p, guard = proxy
    before = guard.block_count
    out = await ask(p.port, f"CONNECT {host} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
    assert out.startswith(b"HTTP/1.1 403")
    assert guard.block_count == before + 1


async def test_plain_http_to_private_dropped(proxy) -> None:
    p, guard = proxy
    req = b"GET http://169.254.169.254/latest HTTP/1.1\r\nHost: 169.254.169.254\r\n\r\n"
    assert await ask(p.port, req) == b""
    assert "169.254.169.254" in guard.since(0)[0]


def test_split_hostport() -> None:
    assert split_hostport("a.b:8080", 443) == ("a.b", 8080)
    assert split_hostport("a.b", 443) == ("a.b", 443)
    assert split_hostport("[::1]:9", 443) == ("::1", 9)
