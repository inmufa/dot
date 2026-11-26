"""SSRF-safe HTTP GET: pinned IP, manual redirects, byte and decompression caps."""

import asyncio
import http.client
import ipaddress
import ssl
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from backend.core.exceptions import DomainException
from backend.core.ssrf import (
    Blocked,
    Resolver,
    Target,
    ip_problem,
    system_resolver,
    vet,
)

FETCH_BLOCKED = 4012
FETCH_FAILED = 4013
FETCH_UNSUPPORTED = 4014
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 5
_REDIRECTS = {301, 302, 303, 307, 308}
_GOOD_TYPES = ("text/", "application/json", "application/xml", "application/xhtml")
_GOOD_SUFFIXES = ("+json", "+xml")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DotAgent/1.0)",
    "Accept": "text/html,text/plain,application/json,application/xml;q=0.9,*/*;q=0.1",
    "Accept-Encoding": "gzip, deflate",
}


@dataclass(frozen=True)
class Policy:
    """What a fetch accepts: headers, content types, caps and time."""

    headers: dict[str, str]
    type_ok: Callable[[str], bool]
    max_bytes: int
    max_redirects: int
    deadline_s: float
    text: bool  # text mode: inflate, reject NUL bytes, truncate instead of failing


IMAGE_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/avif",
        "image/svg+xml",
    }
)
IMAGE_MAX_BYTES = 8 * 1024 * 1024
IMAGE_POLICY = Policy(
    headers={
        "User-Agent": "Mozilla/5.0 (compatible; DotAgent/1.0)",
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,image/svg+xml",
        "Accept-Encoding": "identity",
    },
    type_ok=lambda c: c in IMAGE_TYPES,
    max_bytes=IMAGE_MAX_BYTES,
    max_redirects=3,
    deadline_s=10.0,
    text=False,
)


@dataclass
class Fetched:
    url: str  # final URL
    status: int
    content_type: str
    charset: str
    body: bytes
    truncated: bool
    redirected: bool


def _type_ok(ctype: str) -> bool:
    return ctype.startswith(_GOOD_TYPES) or ctype.endswith(_GOOD_SUFFIXES)


def _inflate(raw: bytes, encoding: str, cap: int) -> tuple[bytes, bool]:
    """Bounded decompression. Returns (data, hit_cap)."""
    if encoding in ("", "identity"):
        return raw[:cap], len(raw) > cap
    if encoding not in ("gzip", "x-gzip", "deflate"):
        raise DomainException(FETCH_UNSUPPORTED, {"detail": f"encoding {encoding}"})
    for wbits in (zlib.MAX_WBITS | 32, -zlib.MAX_WBITS):
        d = zlib.decompressobj(wbits)
        try:
            out = d.decompress(raw, cap + 1)
        except zlib.error:
            continue
        return out[:cap], len(out) > cap or bool(d.unconsumed_tail)
    raise DomainException(FETCH_FAILED, {"detail": "corrupt compressed body"})


def _charset(ctype_header: str) -> str:
    for part in ctype_header.split(";")[1:]:
        k, _, v = part.strip().partition("=")
        if k.lower() == "charset":
            return v.strip("\"' ").lower()
    return ""


def _blocking_stdlib_get(
    t: Target, timeout: float, cap: int, headers: dict[str, str] = _HEADERS
) -> tuple[int, dict[str, str], bytes, tuple[str, int] | None]:
    """Runs in a thread: httpx (httpcore's TLS ClientHello) is fingerprinted and
    blocked by some edges that let an identical request through from Python's
    plain http.client - confirmed live against Wikimedia's edge, same IP, same
    moment. Returns (status, headers, body, peer_addr)."""
    host = f"[{t.host}]" if ":" in t.host else t.host
    conn: http.client.HTTPConnection
    if t.scheme == "https":
        conn = http.client.HTTPSConnection(
            host, t.port, timeout=timeout, context=ssl.create_default_context()
        )
    else:
        conn = http.client.HTTPConnection(host, t.port, timeout=timeout)
    try:
        conn.request("GET", t.path, headers=headers)
        resp = conn.getresponse()
        peer = conn.sock.getpeername() if conn.sock else None
        raw = bytearray()
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            raw += chunk
            if len(raw) > cap:
                break
        return resp.status, dict(resp.getheaders()), bytes(raw), peer
    finally:
        conn.close()


def _finish(
    target: Target,
    status: int,
    header: str,
    raw: bytes,
    encoding: str,
    pol: Policy,
) -> Fetched:
    """Type and size checks shared by both transports."""
    ctype = header.split(";", maxsplit=1)[0].strip().lower()
    if not pol.text:
        if not pol.type_ok(ctype):
            raise DomainException(
                FETCH_UNSUPPORTED, {"detail": f"content type {ctype[:60]}"}
            )
        if len(raw) > pol.max_bytes:
            raise DomainException(FETCH_UNSUPPORTED, {"detail": "too large"})
        return Fetched(
            target.url, status, ctype, "", raw, truncated=False, redirected=False
        )
    if ctype and not pol.type_ok(ctype):
        raise DomainException(
            FETCH_UNSUPPORTED, {"detail": f"content type {ctype[:60]}"}
        )
    body, cut = _inflate(raw[: pol.max_bytes], encoding.strip().lower(), pol.max_bytes)
    if b"\x00" in body[:1024]:
        raise DomainException(FETCH_UNSUPPORTED, {"detail": "binary content"})
    cut = cut or len(raw) > pol.max_bytes
    return Fetched(
        target.url,
        status,
        ctype or "text/plain",
        _charset(header),
        body,
        cut,
        redirected=False,
    )


class SafeFetcher:
    def __init__(
        self,
        *,
        resolver: Resolver = system_resolver,
        allow_loopback: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float = 15.0,
        max_bytes: int = MAX_BYTES,
        deadline_s: float = 30.0,
    ) -> None:
        self._resolver = resolver
        self._allow_loopback = allow_loopback
        self._text = Policy(
            _HEADERS, _type_ok, max_bytes, MAX_REDIRECTS, deadline_s, text=True
        )
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(timeout_s, connect=5.0),
            follow_redirects=False,
            trust_env=False,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _vet(self, url: str) -> Target:
        try:
            return await vet(url, self._resolver, allow_loopback=self._allow_loopback)
        except Blocked as exc:
            raise DomainException(FETCH_BLOCKED, {"detail": str(exc)}) from exc

    def _request(self, t: Target, headers: dict[str, str] = _HEADERS) -> httpx.Request:
        ip = f"[{t.ip}]" if ":" in t.ip else t.ip
        default = 443 if t.scheme == "https" else 80
        host_hdr = t.host if t.port == default else f"{t.host}:{t.port}"
        if ":" in t.host:  # IPv6 literal host
            host_hdr = f"[{t.host}]" + ("" if t.port == default else f":{t.port}")
        return self._client.build_request(
            "GET",
            f"{t.scheme}://{ip}:{t.port}{t.path}",
            headers={**headers, "Host": host_hdr},
            extensions={"sni_hostname": t.host},  # TLS checks the real name
        )

    async def _send_stdlib(self, target: Target, pol: Policy) -> Fetched | str:
        """Fallback for edges that fingerprint-block httpx's TLS handshake itself
        (see _blocking_stdlib_get). Peer is checked against the same SSRF rules
        after connecting, since this path can't pin the IP up front."""
        try:
            status, headers, raw, peer = await asyncio.to_thread(
                _blocking_stdlib_get,
                target,
                self._timeout_s,
                pol.max_bytes,
                pol.headers,
            )
        except (OSError, TimeoutError) as exc:
            raise DomainException(
                FETCH_FAILED, {"detail": f"stdlib fallback: {type(exc).__name__}"}
            ) from exc
        if peer is None:
            raise DomainException(FETCH_BLOCKED, {"detail": "could not verify peer"})
        if problem := ip_problem(ipaddress.ip_address(peer[0]), allow_loopback=False):
            raise DomainException(FETCH_BLOCKED, {"detail": problem})
        low = {k.lower(): v for k, v in headers.items()}
        if status in _REDIRECTS and low.get("location"):
            return low["location"]
        if status >= 400:  # noqa: PLR2004
            raise DomainException(FETCH_FAILED, {"detail": f"HTTP {status}"})
        return _finish(
            target,
            status,
            low.get("content-type", ""),
            raw,
            low.get("content-encoding", ""),
            pol,
        )

    async def _send(self, target: Target, pol: Policy) -> Fetched | str:
        """One hop: a Fetched, or the Location string of a redirect."""
        try:
            resp = await self._client.send(
                self._request(target, pol.headers), stream=True
            )
        except httpx.TimeoutException as exc:
            raise DomainException(FETCH_FAILED, {"detail": "timed out"}) from exc
        except httpx.HTTPError as exc:
            raise DomainException(FETCH_FAILED, {"detail": type(exc).__name__}) from exc
        try:
            if resp.status_code in _REDIRECTS and resp.headers.get("location"):
                return resp.headers["location"]
            if resp.status_code >= 400:  # noqa: PLR2004
                raise DomainException(
                    FETCH_FAILED, {"detail": f"HTTP {resp.status_code}"}
                )
            raw = bytearray()
            async for chunk in resp.aiter_raw():
                raw += chunk
                if len(raw) > pol.max_bytes:
                    break
            return _finish(
                target,
                resp.status_code,
                resp.headers.get("content-type", ""),
                bytes(raw),
                resp.headers.get("content-encoding", ""),
                pol,
            )
        finally:
            await resp.aclose()

    async def get(self, url: str, policy: Policy | None = None) -> Fetched:
        pol = policy or self._text
        current, hops = url, 0
        try:
            async with asyncio.timeout(pol.deadline_s):
                while True:
                    target = await self._vet(current)  # re-vet every hop
                    try:
                        out = await self._send(target, pol)
                    except DomainException as exc:
                        # some edges block httpx's TLS fingerprint itself, not the
                        # page (confirmed live: Wikimedia's - identical request
                        # succeeds via Python's stdlib http.client, same IP, same
                        # moment). Fall back to that, peer re-checked afterwards.
                        if exc.code != FETCH_FAILED or "403" not in str(
                            exc.ctx.get("detail", "")
                        ):
                            raise
                        out = await self._send_stdlib(target, pol)
                    if isinstance(out, Fetched):
                        out.redirected = hops > 0
                        return out
                    hops += 1
                    if hops > pol.max_redirects:
                        raise DomainException(
                            FETCH_FAILED, {"detail": "too many redirects"}
                        )
                    current = urljoin(current, out)
        except TimeoutError as exc:
            raise DomainException(FETCH_FAILED, {"detail": "timed out"}) from exc
