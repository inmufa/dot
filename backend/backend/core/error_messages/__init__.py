from typing import Any

from backend.core.error_messages import core, governance, mcp, session, tools, web

LANGUAGES = ("en", "ru", "uz")
_MODULES = (core, session, governance, tools, web, mcp)


def _merge() -> dict[int, dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for module in _MODULES:
        for code, entry in module.CATALOG.items():
            if code in merged:
                msg = f"duplicate error code {code}"
                raise RuntimeError(msg)
            merged[code] = entry
    return merged


CATALOG = _merge()
