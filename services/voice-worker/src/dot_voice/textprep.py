"""Turn assistant markdown into speakable sentences (no code, URLs, tables)."""

import re

_FENCE = re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)", re.DOTALL)
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_URL = re.compile(r"(?:https?://|www\.)[^\s)>\]]+", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]{3,}\|?\s*$")
_INLINE = re.compile(r"`([^`\n]+)`")
_HTML = re.compile(r"<[^>\n]{1,200}>")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_QUOTE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.MULTILINE)
_EMPH = re.compile(r"(\*\*|__|\*|~~)")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE)
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️]")
_SENT = re.compile(r"(?<=[.!?])[\"')\]]*\s+|\n+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
MAX_INLINE_CODE = 40
MAX_SENTENCE = 240


def _inline_code(m: re.Match[str]) -> str:
    body = m.group(1).strip()
    if len(body) > MAX_INLINE_CODE or not re.fullmatch(r"[\w.\-/ ]+", body):
        return " code omitted "
    body = _CAMEL.sub(" ", body)
    return re.sub(r"\s+", " ", body.replace("_", " ").replace("/", " slash "))


def _drop_tables(text: str) -> str:
    out: list[str] = []
    in_table = False
    for line in text.split("\n"):
        if _TABLE_ROW.match(line) or _TABLE_SEP.match(line):
            if not in_table:
                out.append("Table omitted.")
            in_table = True
            continue
        in_table = False
        out.append(line)
    return "\n".join(out)


def clean_for_speech(text: str) -> str:
    """Strip markdown, code, URLs and tables; keep prose. Idempotent enough."""
    text = _FENCE.sub("\n Code omitted.\n", text)
    text = _drop_tables(text)
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("a link", text)
    text = _INLINE.sub(_inline_code, text)
    text = _HTML.sub(" ", text)
    text = _RULE.sub("", text)
    text = _HEADING.sub("", text)
    text = _QUOTE.sub("", text)
    text = _BULLET.sub("", text)
    text = _EMPH.sub("", text)
    text = _EMOJI.sub("", text)
    lines = [ln.strip() for ln in text.split("\n")]
    # a line without end punctuation (heading, list item) must still end a sentence
    lines = [ln + "." if ln and ln[-1] not in ".!?:;," else ln for ln in lines if ln]
    return re.sub(r"[ \t]+", " ", " ".join(lines)).strip()


def _wrap(sentence: str) -> list[str]:
    if len(sentence) <= MAX_SENTENCE:
        return [sentence]
    parts, cur = [], ""
    for piece in re.split(r"(?<=[,;:])\s+", sentence):
        if cur and len(cur) + len(piece) > MAX_SENTENCE:
            parts.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    if cur:
        parts.append(cur)
    out: list[str] = []
    for part in parts:
        rest = part
        while len(rest) > MAX_SENTENCE:
            cut = rest.rfind(" ", 0, MAX_SENTENCE) or MAX_SENTENCE
            out.append(rest[:cut])
            rest = rest[cut:].strip()
        out.append(rest)
    return out


def split_sentences(text: str) -> list[str]:
    """Sentence-sized chunks for streaming synthesis (short ones are merged)."""
    raw = [s.strip() for s in _SENT.split(text) if s and s.strip()]
    chunks: list[str] = []
    for s in raw:
        if chunks and len(chunks[-1]) < 12 and len(chunks[-1]) + len(s) < MAX_SENTENCE:  # noqa: PLR2004
            chunks[-1] = f"{chunks[-1]} {s}"
        else:
            chunks.append(s)
    return [w for c in chunks for w in _wrap(c) if re.search(r"\w", w)]
