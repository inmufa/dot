"""Backend-side SSRF guard: URL vetting and DNS resolution (resolve once, pin the IP)."""

import asyncio
import ipaddress
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

Resolver = Callable[[str, int], Awaitable[list[str]]]
IP = ipaddress.IPv4Address | ipaddress.IPv6Address
_NUMERIC_HOST = re.compile(r"^[0-9][0-9a-fx.]*$", re.IGNORECASE)
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".lan")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIX_TO_FOUR = ipaddress.ip_network("2002::/16")
_COMPAT_V4 = ipaddress.ip_network("::/96")  # deprecated IPv4-compatible
_EXTRA_DENY = tuple(
    ipaddress.ip_network(n)
    for n in ("fec0::/10", "192.88.99.0/24", "5f00::/16", "3fff::/20", "2001::/23")
)
_MAX_URL = 4096


class Blocked(Exception):  # noqa: N818
    """The URL or its resolved address may not be fetched."""


@dataclass(frozen=True)
class Target:
    """A vetted request target: connect to `ip`, speak for `host`."""

    url: str
    scheme: str
    host: str
    port: int
    ip: str
    path: str  # path + query, never empty


def _embedded_v4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip in _SIX_TO_FOUR:
        return ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF)
    if ip in _COMPAT_V4 and int(ip) > 1:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def ip_problem(ip: IP, *, allow_loopback: bool = False) -> str | None:
    """Why the address is off limits, or None for a public unicast address."""
    if isinstance(ip, ipaddress.IPv6Address) and (inner := _embedded_v4(ip)):
        return ip_problem(inner, allow_loopback=allow_loopback)
    if allow_loopback and ip.is_loopback:
        return None
    if any(ip.version == n.version and ip in n for n in _EXTRA_DENY):
        return "non-public address"
    checks = (
        (ip.is_loopback, "loopback address"),
        (ip.is_multicast, "multicast address"),
        (ip.is_link_local, "link-local address"),
        (not ip.is_global, "non-public address"),  # private, CGNAT, ULA, reserved
    )
    return next((why for hit, why in checks if hit), None)


def _numeric_ip(host: str) -> IP | None:
    """Parse plain and obfuscated IPs (decimal, hex, octal, short forms)."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if not _NUMERIC_HOST.match(host):
        return None
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError as exc:
        msg = "malformed numeric host"
        raise Blocked(msg) from exc


def split_url(url: str) -> tuple[SplitResult, str, int]:
    """Syntax checks. Returns (parts, normalised host, port)."""
    if len(url) > _MAX_URL or any(c in url for c in "\r\n\t\x00 "):
        msg = "malformed URL"
        raise Blocked(msg)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        msg = "malformed URL"
        raise Blocked(msg) from exc
    if parts.scheme not in ("http", "https"):
        msg = "only http and https URLs are allowed"
        raise Blocked(msg)
    if "@" in parts.netloc:
        msg = "credentials in the URL are not allowed"
        raise Blocked(msg)
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        msg = "URL has no host"
        raise Blocked(msg)
    return parts, host, port or (443 if parts.scheme == "https" else 80)


def _vet_name(host: str) -> IP | None:
    ip = _numeric_ip(host)
    if ip is not None:
        return ip
    if host == "localhost" or host.endswith(_LOCAL_SUFFIXES) or "." not in host:
        msg = "local host name"
        raise Blocked(msg)
    return None


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        msg = "host name does not resolve"
        raise Blocked(msg) from exc
    return list(dict.fromkeys(str(i[4][0]) for i in infos))


async def vet(
    url: str, resolver: Resolver = system_resolver, *, allow_loopback: bool = False
) -> Target:
    """Vet a URL and pin it to one vetted address; every resolved address must pass."""
    parts, host, port = split_url(url)
    literal = _vet_name(host)
    addrs = [str(literal)] if literal else await resolver(host, port)
    if not addrs:
        msg = "host name does not resolve"
        raise Blocked(msg)
    parsed: list[IP] = []
    for raw in addrs:
        try:
            parsed.append(ipaddress.ip_address(raw.split("%")[0]))
        except ValueError as exc:
            msg = "resolver returned a bad address"
            raise Blocked(msg) from exc
    for ip in parsed:
        if reason := ip_problem(ip, allow_loopback=allow_loopback):
            msg = f"{reason} is not allowed"
            raise Blocked(msg)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return Target(url, parts.scheme, host, port, str(parsed[0]), path)
