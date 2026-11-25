"""Plain-text hygiene for widget strings: no control tags, no HTML, no script URLs."""

import re
import unicodedata

# Zero-width, bidi and other invisible formatting characters.
_INVISIBLE = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\u00ad]"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_CONTROL_TAGS = re.compile(
    r"</?\s*(system-reminder|tool_call|tool_response|think|function|parameter)\b[^>]*>?",
    re.IGNORECASE,
)
_HTML_TAGS = (
    "script|iframe|object|embed|style|link|meta|svg|math|img|a|div|span|p|b|i|u|"
    "form|input|button|body|html|head|base|video|audio|source|template|textarea|"
    "select|option|frame|frameset|applet|details|table|tr|td|ul|ol|li|h[1-6]|br|"
    "center|font|marquee|canvas|noscript"
)
_HTML = re.compile(rf"<\s*/?\s*(?:{_HTML_TAGS})\b[^<>]*>?", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--|<!\[CDATA\[|<\?", re.IGNORECASE)
_SCRIPT_URL = re.compile(r"(javascript|vbscript|data\s*:\s*text/html)\s*:?", re.I)
_EVENT_ATTR = re.compile(r"\bon[a-z]{3,20}\s*=", re.IGNORECASE)


class UnsafeText(ValueError):  # noqa: N818
    """Text that looks like markup or a script; the model must resend plain text."""


def clean(text: str, max_len: int) -> str:
    """Normalise one widget string or raise ValueError describing the problem."""
    out = unicodedata.normalize("NFC", text)
    out = _INVISIBLE.sub("", out)
    out = _CONTROL.sub("", out)
    out = _CONTROL_TAGS.sub("", out).replace("\r\n", "\n")
    squashed = re.sub(r"\s+", "", out)
    if _HTML.search(out) or _HTML_COMMENT.search(out):
        msg = "contains HTML; send plain text only"
        raise UnsafeText(msg)
    if _SCRIPT_URL.search(squashed) or _EVENT_ATTR.search(out):
        msg = "contains a script or javascript: URL; send plain text only"
        raise UnsafeText(msg)
    out = out.strip()
    if len(out) > max_len:
        msg = f"is too long ({len(out)} chars, max {max_len})"
        raise ValueError(msg)
    return out


def soft_clean(text: str, max_len: int) -> str:
    """For user-typed answers: drop invisible chars and control tags, never reject."""
    out = unicodedata.normalize("NFC", text)
    out = _CONTROL.sub("", _INVISIBLE.sub("", out))
    return _CONTROL_TAGS.sub("", out).strip()[:max_len]
