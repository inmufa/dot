"""SSRF guard: scheme, host rules, resolved-IP checks with a short DNS pin."""

import asyncio
import ipaddress
import socket
import time
from collections import deque
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from dot_browser.settings import Settings

Resolver = Callable[[str], Awaitable[list[str]]]
IP = ipaddress.IPv4Address | ipaddress.IPv6Address

METADATA = {"169.254.169.254", "100.100.100.200", "fd00:ec2::254"}
BLOCKED_NAMES = ("localhost", "metadata.google.internal")
BLOCKED_SUFFIXES = (".localhost", ".internal", ".local")
NAT64 = ipaddress.ip_network("64:ff9b::/96")
SIX_TO_FOUR = ipaddress.ip_network("2002::/16")
COMPAT_V4 = ipaddress.ip_network("::/96")
EXTRA_DENY = tuple(
    ipaddress.ip_network(n) for n in ("fec0::/10", "192.88.99.0/24", "2001::/23")
)


class Blocked(Exception):  # noqa: N818
    """Raised when a URL or address is refused."""


async def system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({str(i[4][0]).split("%")[0] for i in infos})


def _embedded(ip: IP) -> list[IP]:
    """IPv4 addresses hidden inside mapped / NAT64 / 6to4 IPv6 forms."""
    if isinstance(ip, ipaddress.IPv4Address):
        return []
    out: list[IP] = []
    if ip.ipv4_mapped:
        out.append(ip.ipv4_mapped)
    if ip in NAT64:
        out.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    if ip in SIX_TO_FOUR:
        out.append(ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF))
    if ip in COMPAT_V4 and int(ip) > 1:
        out.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return out


def ip_blocked(raw: str, *, allow_loopback: bool = False) -> bool:
    try:
        ip = ipaddress.ip_address(raw.split("%", maxsplit=1)[0])
    except ValueError:
        return True
    if allow_loopback and ip.is_loopback:
        return False
    if str(ip) in METADATA or not ip.is_global:
        return True
    if any(ip.version == n.version and ip in n for n in EXTRA_DENY):
        return True
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    return any(
        ip_blocked(str(inner), allow_loopback=allow_loopback) for inner in _embedded(ip)
    )


def _matches(host: str, rules: list[str]) -> bool:
    return any(host == r or host.endswith("." + r) for r in rules)


def _rules(raw: str) -> list[str]:
    return [r.strip().lower().lstrip(".") for r in raw.split(",") if r.strip()]


class UrlGuard:
    def __init__(
        self,
        settings: Settings,
        resolver: Resolver | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.resolver = resolver or system_resolver
        self.clock = clock
        self.allow = _rules(settings.allow_hosts)
        self.deny = _rules(settings.deny_hosts)
        self._pins: dict[str, tuple[float, list[str]]] = {}
        self.block_count = 0
        self._recent: deque[str] = deque(maxlen=50)

    def note(self, reason: str) -> None:
        self.block_count += 1
        self._recent.append(reason)

    def since(self, mark: int) -> list[str]:
        """Reasons logged after `mark` (a block_count value), oldest first."""
        n = min(self.block_count - mark, len(self._recent))
        return list(self._recent)[len(self._recent) - n :] if n > 0 else []

    async def resolve_public(self, host: str) -> list[str]:
        """Fresh resolve of `host`, all addresses vetted; the caller connects to these."""
        host = host.rstrip(".").lower()
        self._check_rules(host.strip("[]"))
        return await self._check_address(host, fresh=True)

    async def check(self, url: str, *, navigation: bool) -> None:
        try:
            parts = urlsplit(url)
            host = (parts.hostname or "").rstrip(".").lower()
        except ValueError as exc:
            msg = "malformed url"
            raise Blocked(msg) from exc
        scheme = parts.scheme.lower()
        if scheme in ("data", "blob") and not navigation:
            return
        if url == "about:blank":
            return
        if scheme not in ("http", "https"):
            msg = f"scheme not allowed: {scheme or 'none'}"
            raise Blocked(msg)
        if not host:
            msg = "url has no host"
            raise Blocked(msg)
        self._check_rules(host)
        await self._check_address(host)

    def _check_rules(self, host: str) -> None:
        if _matches(host, self.deny):
            msg = f"host denied: {host}"
            raise Blocked(msg)
        if self.allow and not _matches(host, self.allow):
            msg = f"host not in allowlist: {host}"
            raise Blocked(msg)

    async def _check_address(self, host: str, *, fresh: bool = False) -> list[str]:
        loop_ok = self.settings.unsafe_allow_loopback
        if not (loop_ok and host == "localhost") and (
            host in BLOCKED_NAMES or host.endswith(BLOCKED_SUFFIXES)
        ):
            msg = f"internal hostname blocked: {host}"
            raise Blocked(msg)
        bare = host.strip("[]")
        try:
            ipaddress.ip_address(bare)
        except ValueError:
            addrs = await self._resolve(host, fresh=fresh)
        else:
            addrs = [bare]
        if not addrs:
            msg = f"host did not resolve: {host}"
            raise Blocked(msg)
        for addr in addrs:
            if ip_blocked(addr, allow_loopback=loop_ok):
                msg = f"address not allowed: {host} -> {addr}"
                raise Blocked(msg)
        return addrs

    async def _resolve(self, host: str, *, fresh: bool) -> list[str]:
        now = self.clock()
        hit = self._pins.get(host)
        if hit and not fresh and now - hit[0] < self.settings.dns_pin_seconds:
            return hit[1]
        try:
            addrs = await self.resolver(host)
        except OSError as exc:
            msg = f"dns failure: {host}"
            raise Blocked(msg) from exc
        # Pin only a fully public answer; a bad one is re-resolved next time.
        if addrs and not any(ip_blocked(a) for a in addrs):
            self._pins[host] = (now, addrs)
        return addrs
