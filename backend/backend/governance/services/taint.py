"""Stage B: per-session taint store (no LLM). Untrusted text must not steer writes."""

import json
import re
from dataclasses import dataclass, field
from typing import Any

MIN_OVERLAP = 12
_MAX_TEXTS_CHARS = 400_000  # per session, oldest text is dropped first
_MAX_SCAN = 200_000  # chars of arguments inspected per call


@dataclass
class _SessionTaint:
    texts: list[str] = field(default_factory=list)
    grams: set[int] = field(default_factory=set)
    total: int = 0
    since_user: bool = False  # tainted input arrived after the last user turn
    user_urls: set[str] = field(default_factory=set)  # URLs the user typed himself


_URL = re.compile(r"https?://[^\s<>\"')\]]+")


def _interesting(gram: str) -> bool:
    return bool(gram.strip()) and len(set(gram)) >= 3  # noqa: PLR2004


def _grams(text: str) -> set[int]:
    return {
        hash(text[i : i + MIN_OVERLAP])
        for i in range(max(0, len(text) - MIN_OVERLAP + 1))
        if _interesting(text[i : i + MIN_OVERLAP])
    }


def _flatten(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _flatten(v)]
    if isinstance(value, list | tuple):
        return [s for v in value for s in _flatten(v)]
    return [json.dumps(value)] if value is not None else []


class TaintStore:
    def __init__(self) -> None:
        self._sessions: dict[str, _SessionTaint] = {}

    def _get(self, session: str) -> _SessionTaint:
        return self._sessions.setdefault(session, _SessionTaint())

    def add(self, session: str, text: str) -> None:
        """Register untrusted content that just entered the model context."""
        st = self._get(session)
        st.since_user = True
        if not text:
            return
        st.texts.append(text)
        st.total += len(text)
        st.grams |= _grams(text)
        if st.total > _MAX_TEXTS_CHARS:
            while st.total > _MAX_TEXTS_CHARS and len(st.texts) > 1:
                st.total -= len(st.texts.pop(0))
            st.grams = set().union(*(_grams(t) for t in st.texts))

    def has_taint(self, session: str) -> bool:
        """Any untrusted input is in play (including an inherited flag)."""
        st = self._sessions.get(session)
        return bool(st and (st.texts or st.since_user))

    def consumed(self, session: str) -> bool:
        """Untrusted text actually entered this session's context."""
        st = self._sessions.get(session)
        return bool(st and st.texts)

    def user_turn(self, session: str, text: str = "") -> None:
        """A real user message resets the 'follows tainted input' flag."""
        st = self._get(session)
        st.since_user = False
        st.user_urls |= {u.lower().rstrip("/") for u in _URL.findall(text)}

    def url_known(self, session: str, url: str) -> bool:
        """The URL came from the user or appears verbatim in untrusted content."""
        st = self._sessions.get(session)
        if st is None:
            return False
        key = url.split("#", 1)[0].lower().rstrip("/")
        if key in st.user_urls:
            return True
        return any(key in t.lower() for t in st.texts)

    def reset(self, session: str) -> None:
        self._sessions.pop(session, None)

    def check(self, session: str, args: dict[str, Any]) -> str | None:
        """Reason to escalate a mutating call, or None when it looks clean."""
        st = self._sessions.get(session)
        if st is None:
            return None
        if st.since_user:
            return "follows untrusted input with no user turn in between"
        return self.overlap(session, args)

    def overlap(self, session: str, args: dict[str, Any]) -> str | None:
        """Reason when the arguments repeat a run of untrusted text."""
        st = self._sessions.get(session)
        if st is None:
            return None
        scanned = 0
        for text in _flatten(args):
            for i in range(max(0, len(text) - MIN_OVERLAP + 1)):
                scanned += 1
                gram = text[i : i + MIN_OVERLAP]
                if hash(gram) in st.grams and _interesting(gram):
                    return f"arguments repeat untrusted text ({gram[:20]!r}...)"
                if scanned > _MAX_SCAN:
                    return None
        return None
