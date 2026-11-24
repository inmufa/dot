"""Crockford Base32 time-sortable public ids: Letter + 5 minute chars + 4 random."""

import secrets
import time

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
EPOCH = 1_767_225_600  # 2026-01-01T00:00:00Z
_TIME_CHARS = 5
_RANDOM_CHARS = 4


def _encode(value: int, width: int) -> str:
    chars = []
    for _ in range(width):
        value, rem = divmod(value, 32)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def new_public_id(letter: str, now: float | None = None) -> str:
    if len(letter) != 1 or letter not in ALPHABET:
        msg = f"invalid public id letter: {letter!r}"
        raise ValueError(msg)
    minutes = int(((now if now is not None else time.time()) - EPOCH) // 60)
    if minutes < 0 or minutes >= 32**_TIME_CHARS:
        msg = "time out of range for public id"
        raise ValueError(msg)
    rand = "".join(secrets.choice(ALPHABET) for _ in range(_RANDOM_CHARS))
    return f"{letter}{_encode(minutes, _TIME_CHARS)}{rand}"
