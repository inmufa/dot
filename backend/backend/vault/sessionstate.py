"""Storage-state hygiene: scope to origins, drop expired, cap lifetime."""

import json
import time
from datetime import UTC, datetime
from typing import Any

from backend.vault.origins import cookie_in_scope, origin_of

MAX_STATE_BYTES = 1_500_000


def aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt and dt.tzinfo is None else dt


def tidy(
    raw: dict[str, Any],
    origins: list[str],
    max_age_days: float,
    now: float | None = None,
) -> tuple[dict[str, Any], float | None]:
    """Return (state kept, latest expiry epoch). Empty cookies means nothing usable.

    Session cookies become persistent, capped at `max_age_days` like every other cookie.
    """
    now = time.time() if now is None else now
    cap = now + max_age_days * 86_400
    cookies, latest = [], 0.0
    for c in raw.get("cookies", []):
        if not cookie_in_scope(str(c.get("domain", "")), origins):
            continue
        exp = float(c.get("expires", -1))
        if 0 < exp <= now:
            continue
        exp = cap if exp <= 0 else min(exp, cap)
        cookies.append({**c, "expires": exp})
        latest = max(latest, exp)
    bound = {origin_of(o) for o in origins}
    stores = [
        {"origin": o["origin"], "localStorage": o["localStorage"]}
        for o in raw.get("origins", [])
        if origin_of(str(o.get("origin", ""))) in bound and o.get("localStorage")
    ]
    state = {"cookies": cookies, "origins": stores}
    if not cookies or len(json.dumps(state)) > MAX_STATE_BYTES:
        return {"cookies": [], "origins": []}, None
    return state, latest


def secret_values(state: dict[str, Any]) -> list[str]:
    """Cookie values worth masking in logs while the state is in memory."""
    return [str(c.get("value", "")) for c in state.get("cookies", [])]
