from typing import Any

from backend.core.api.language import DEFAULT_LANGUAGE
from backend.core.error_messages import CATALOG

UNKNOWN_CODE = 1000


def build_envelope(
    code: int,
    lang: str,
    *,
    key: str | None = None,
    error_type: str = "domain_error",
    text: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Return (http status, one envelope entry) for a catalog code."""
    code = code if code in CATALOG else UNKNOWN_CODE
    entry = CATALOG[code]
    messages = entry["messages"]
    body = {
        "key": key,
        "code": code,
        "show": entry["show"],
        "icon_type": "error",
        "type": error_type,
        "messages": [text or messages.get(lang) or messages[DEFAULT_LANGUAGE]],
    }
    return entry["status"], body
