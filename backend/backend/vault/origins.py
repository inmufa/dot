"""Origin normalisation and matching (exact scheme + host + port, punycode host)."""

from urllib.parse import urlsplit

_PORTS = {"http": 80, "https": 443}


def origin_of(url: str) -> str | None:
    if not url or len(url) > 4096:  # noqa: PLR2004
        return None
    try:
        parts = urlsplit(url.strip())
        scheme, port = parts.scheme.lower(), parts.port
        host = (parts.hostname or "").rstrip(".").lower()
        host = host.encode("idna").decode("ascii") if host else ""
    except (ValueError, UnicodeError):
        return None
    if scheme not in _PORTS or not host:
        return None
    host = f"[{host}]" if ":" in host else host
    return f"{scheme}://{host}" + ("" if port in (None, _PORTS[scheme]) else f":{port}")


def matches(url: str, origins: list[str]) -> bool:
    found = origin_of(url)
    return found is not None and found in {origin_of(o) for o in origins}


def clean_origins(raw: list[str], *, allow_http: bool) -> list[str]:
    """Canonical, deduplicated, https-only origin list; ValueError on anything else."""
    out: list[str] = []
    for item in raw:
        found = origin_of(item)
        if found is None or (found.startswith("http://") and not allow_http):
            msg = "invalid origin"
            raise ValueError(msg)
        if found not in out:
            out.append(found)
    if not out:
        msg = "at least one origin is required"
        raise ValueError(msg)
    return out


def cookie_in_scope(domain: str, origins: list[str]) -> bool:
    d = domain.lstrip(".").lower()
    for origin in origins:
        host = (urlsplit(origin).hostname or "").lower()
        if d and (host == d or (host.endswith("." + d) and "." in d)):
            return True
    return False
