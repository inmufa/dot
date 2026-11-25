"""Origin parsing and matching. Exact scheme + host + port; no suffix or wildcard rules."""

from urllib.parse import urlsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}
_MAX_URL = 4096


def origin_of(url: str) -> str | None:
    """Canonical `scheme://host[:port]` (punycode host, default port dropped) or None."""
    if not url or len(url) > _MAX_URL:
        return None
    try:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").rstrip(".").lower()
        port = parts.port
    except ValueError:
        return None
    if scheme not in _DEFAULT_PORTS or not host:
        return None
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if ":" in host:
        host = f"[{host}]"
    suffix = "" if port in (None, _DEFAULT_PORTS[scheme]) else f":{port}"
    return f"{scheme}://{host}{suffix}"


def origin_matches(url: str, origins: list[str]) -> bool:
    found = origin_of(url)
    return found is not None and found in {origin_of(o) for o in origins}


def host_of(origin: str) -> str:
    return (urlsplit(origin).hostname or "").lower()


def cookie_in_scope(domain: str, origins: list[str]) -> bool:
    """True when a cookie with this Domain attribute is sent to one of the origins' hosts."""
    d = domain.lstrip(".").lower()
    if not d:
        return False
    for origin in origins:
        host = host_of(origin)
        if host == d or (host.endswith("." + d) and "." in d):
            return True
    return False
