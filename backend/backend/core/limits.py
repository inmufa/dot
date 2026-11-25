"""A context limit that may be a constant or a live value (probed from llama-server)."""

from collections.abc import Callable

LimitSource = int | Callable[[], int]


def read_limit(source: LimitSource) -> int:
    return source() if callable(source) else source
