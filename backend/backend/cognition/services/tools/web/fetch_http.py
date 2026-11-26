"""SSRF-safe HTTP GET: pinned IP, manual redirects, byte and decompression caps."""

import asyncio
import ipaddress
import zlib
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
        self._deadline = deadline_s
        self._resolver = resolver
        self._allow_loopback = allow_loopback
        self._max = max_bytes
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

    def _request(self, t: Target) -> httpx.Request:
        ip = f"[{t.ip}]" if ":" in t.ip else t.ip
        default = 443 if t.scheme == "https" else 80
        host_hdr = t.host if t.port == default else f"{t.host}:{t.port}"
        if ":" in t.host:  # IPv6 literal host
            host_hdr = f"[{t.host}]" + ("" if t.port == default else f":{t.port}")
        return self._client.build_request(
            "GET",
            f"{t.scheme}://{ip}:{t.port}{t.path}",
            headers={**_HEADERS, "Host": host_hdr},
            extensions={"sni_hostname": t.host},  # TLS checks the real name
        )

    def _request_normal(self, t: Target) -> httpx.Request:
        """Same request, but by hostname: lets the client do its own DNS and TLS,
        for sites whose edge blocks the pinned-IP-plus-spoofed-Host pattern above as
        suspicious. The connected peer is checked against the same rules afterwards
        (_verify_peer), so this doesn't skip SSRF protection, just defers it."""
        return self._client.build_request(
            "GET", f"{t.scheme}://{t.host}:{t.port}{t.path}", headers=_HEADERS
        )

    def _verify_peer(self, resp: httpx.Response) -> None:
        stream = resp.extensions.get("network_stream")
        addr = stream.get_extra_info("server_addr") if stream else None
        if not addr:
            raise DomainException(FETCH_BLOCKED, {"detail": "could not verify peer"})
        if problem := ip_problem(ipaddress.ip_address(addr[0]), allow_loopback=False):
            raise DomainException(FETCH_BLOCKED, {"detail": problem})

    async def _send(self, target: Target, *, direct: bool = False) -> Fetched | str:
        """One hop: a Fetched, or the Location string of a redirect."""
        req = self._request_normal(target) if direct else self._request(target)
        try:
            resp = await self._client.send(req, stream=True)
        except httpx.TimeoutException as exc:
            raise DomainException(FETCH_FAILED, {"detail": "timed out"}) from exc
        except httpx.HTTPError as exc:
            raise DomainException(FETCH_FAILED, {"detail": type(exc).__name__}) from exc
        try:
            if direct:
                self._verify_peer(resp)
            if resp.status_code in _REDIRECTS and resp.headers.get("location"):
                return resp.headers["location"]
            if resp.status_code >= 400:  # noqa: PLR2004
                raise DomainException(
                    FETCH_FAILED, {"detail": f"HTTP {resp.status_code}"}
                )
            header = resp.headers.get("content-type", "")
            ctype = header.split(";")[0].strip().lower()
            if ctype and not _type_ok(ctype):
                raise DomainException(
                    FETCH_UNSUPPORTED, {"detail": f"content type {ctype[:60]}"}
                )
            raw = bytearray()
            async for chunk in resp.aiter_raw():
                raw += chunk
                if len(raw) > self._max:
                    break
            encoding = resp.headers.get("content-encoding", "").strip().lower()
            body, cut = _inflate(bytes(raw[: self._max]), encoding, self._max)
            if b"\x00" in body[:1024]:
                raise DomainException(FETCH_UNSUPPORTED, {"detail": "binary content"})
            cut = cut or len(raw) > self._max
            return Fetched(
                target.url,
                resp.status_code,
                ctype or "text/plain",
                _charset(header),
                body,
                cut,
                redirected=False,
            )
        finally:
            await resp.aclose()

    async def get(self, url: str) -> Fetched:
        current, hops = url, 0
        try:
            async with asyncio.timeout(self._deadline):
                while True:
                    target = await self._vet(current)  # re-vet every hop
                    try:
                        out = await self._send(target)
                    except DomainException as exc:
                        # some edges block the pinned-IP-plus-Host pattern itself as
                        # suspicious (e.g. Wikimedia's: HTTP 403 from its own edge,
                        # not the article). One retry by hostname, peer re-checked.
                        if exc.code != FETCH_FAILED or "403" not in str(
                            exc.ctx.get("detail", "")
                        ):
                            raise
                        out = await self._send(target, direct=True)
                    if isinstance(out, Fetched):
                        out.redirected = hops > 0
                        return out
                    hops += 1
                    if hops > MAX_REDIRECTS:
                        raise DomainException(
                            FETCH_FAILED, {"detail": "too many redirects"}
                        )
                    current = urljoin(current, out)
        except TimeoutError as exc:
            raise DomainException(FETCH_FAILED, {"detail": "timed out"}) from exc
