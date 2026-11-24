"""Local forward proxy Chromium is forced through.

Each connection resolves the host, vets every address and connects to that very
address, so a DNS answer cannot change between check and connect (rebinding).
Redirect hops arrive as new proxy requests and are vetted the same way.
"""

import asyncio
import contextlib
from urllib.parse import urlsplit

from dot_browser.guard import Blocked, UrlGuard
from dot_browser.settings import Settings

HEAD_LIMIT = 65_536
CHUNK = 65_536
DROP = {"proxy-connection", "proxy-authorization", "connection", "keep-alive"}


def split_hostport(target: str, default_port: int) -> tuple[str, int]:
    if target.startswith("["):
        host, _, rest = target[1:].partition("]")
        return host, int(rest[1:]) if rest.startswith(":") else default_port
    host, sep, port = target.rpartition(":")
    return (host, int(port)) if sep and port.isdigit() else (target, default_port)


class EgressProxy:
    def __init__(self, guard: UrlGuard, cfg: Settings) -> None:
        self.guard = guard
        self.cfg = cfg
        self._server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

    async def _client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await asyncio.wait_for(
                self._serve(reader, writer), self.cfg.proxy_timeout_s
            )
        except (TimeoutError, OSError, ValueError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        head = await reader.readuntil(b"\r\n\r\n")
        if len(head) > HEAD_LIMIT:
            return
        lines = head.decode("latin-1").split("\r\n")
        method, target, version = lines[0].split(" ", 2)
        try:
            if method.upper() == "CONNECT":
                host, port = split_hostport(target, 443)
                up = await self._open(host, port)
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            else:
                parts = urlsplit(target)
                host, port = parts.hostname or "", parts.port or 80
                up = await self._open(host, port)
                path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
                up[1].write(self._rewrite(method, path, version, lines[1:]))
        except Blocked as exc:
            self.guard.note(str(exc))
            if method.upper() == "CONNECT":
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            return
        await self._pipe(reader, writer, *up)

    async def _open(
        self, host: str, port: int
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if not host:
            msg = "proxy request without host"
            raise Blocked(msg)
        addrs = await self.guard.resolve_public(host)
        last: OSError | None = None
        for addr in addrs:
            try:
                return await asyncio.wait_for(
                    asyncio.open_connection(addr, port), self.cfg.proxy_connect_s
                )
            except (TimeoutError, OSError) as exc:
                last = exc if isinstance(exc, OSError) else OSError("connect timeout")
        raise last or OSError("no address")

    @staticmethod
    def _rewrite(method: str, path: str, version: str, headers: list[str]) -> bytes:
        keep = [
            h for h in headers if h and h.split(":", 1)[0].strip().lower() not in DROP
        ]
        return "\r\n".join(
            [f"{method} {path} {version}", *keep, "Connection: close", "", ""]
        ).encode("latin-1")

    async def _pipe(
        self,
        creader: asyncio.StreamReader,
        cwriter: asyncio.StreamWriter,
        ureader: asyncio.StreamReader,
        uwriter: asyncio.StreamWriter,
    ) -> None:
        cap = self.cfg.max_response_bytes
        up = asyncio.create_task(_copy(creader, uwriter, None))
        down = asyncio.create_task(_copy(ureader, cwriter, cap))
        await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
        for task in (up, down):
            task.cancel()
        uwriter.close()


async def _copy(
    src: asyncio.StreamReader, dst: asyncio.StreamWriter, cap: int | None
) -> None:
    sent = 0
    with contextlib.suppress(OSError, asyncio.CancelledError):
        while chunk := await src.read(CHUNK):
            sent += len(chunk)
            if cap is not None and sent > cap:
                return
            dst.write(chunk)
            await dst.drain()
