"""In-memory token bucket per client for chat starts (single-process, single-user)."""

import math
import time
from collections.abc import Callable

from fastapi import Request

from backend.core.exceptions import DomainException

RATE_LIMITED = 1004
MESSAGE_TOO_LONG = 1010
_MAX_CLIENTS = 1024


class TokenBucket:
    def __init__(
        self, per_minute: float, burst: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._rate = per_minute / 60.0
        self._burst = float(burst)
        self._clock = clock
        self._state: dict[str, tuple[float, float]] = {}

    def take(self, key: str) -> float:
        """Return 0 when a token was taken, else seconds until one is available."""
        now = self._clock()
        tokens, last = self._state.get(key, (self._burst, now))
        tokens = min(self._burst, tokens + (now - last) * self._rate)
        if tokens >= 1.0:
            self._state[key] = (tokens - 1.0, now)
            self._evict(now)
            return 0.0
        self._state[key] = (tokens, now)
        return (1.0 - tokens) / self._rate

    def _evict(self, now: float) -> None:
        if len(self._state) <= _MAX_CLIENTS:
            return
        full_after = self._burst / self._rate
        self._state = {k: v for k, v in self._state.items() if now - v[1] < full_after}


def enforce_chat_rate(request: Request) -> None:
    """Raise 1004 with Retry-After when this client starts chats too fast."""
    state = request.app.state
    bucket = getattr(state, "chat_bucket", None)
    if bucket is None:
        cfg = state.settings
        bucket = state.chat_bucket = TokenBucket(
            cfg.chat_rate_per_min, cfg.chat_rate_burst
        )
    client = request.client.host if request.client else "-"
    wait = bucket.take(client)
    if wait:
        raise DomainException(RATE_LIMITED, retry_after=max(1, math.ceil(wait)))
