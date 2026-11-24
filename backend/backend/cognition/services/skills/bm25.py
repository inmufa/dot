"""Pure-python BM25 over a handful of short documents."""

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an and are as at be by for from how i in is it me my of on or the this "
    "that to use used using when with you your can do does please want need "
    "user users any all what which about there their".split()
)
K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    out = []
    for tok in _TOKEN.findall(text.lower()):
        if tok in _STOP or len(tok) < 2:
            continue
        out.append(_stem(tok))
    return out


def _stem(tok: str) -> str:
    for suffix in ("ing", "es", "s", "ed"):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= 4:
            return tok[: -len(suffix)]
    return tok


class Bm25:
    def __init__(self, docs: dict[str, list[str]]) -> None:
        self._tf = {k: Counter(v) for k, v in docs.items()}
        self._len = {k: len(v) for k, v in docs.items()}
        n = max(len(docs), 1)
        self._avg = sum(self._len.values()) / n or 1.0
        df: Counter[str] = Counter()
        for tf in self._tf.values():
            df.update(tf.keys())
        self._idf = {
            t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()
        }

    def scores(self, query: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, tf in self._tf.items():
            norm = 1 - B + B * self._len[key] / self._avg
            total = 0.0
            for term in set(query):
                f = tf.get(term, 0)
                if f:
                    total += self._idf[term] * f * (K1 + 1) / (f + K1 * norm)
            if total:
                out[key] = total
        return out
