"""Upload allowlist: extension decides the type, magic bytes must agree."""

import re
import struct
import unicodedata
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from backend.core.exceptions import DomainException

UNSUPPORTED = 4101
MISMATCH = 4104
EMPTY = 4113
Kind = Literal["image", "document", "text", "data"]

_IMAGES = {
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    "jpg": ("image/jpeg", b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    "gif": ("image/gif", b"GIF8"),
    "webp": ("image/webp", b"RIFF"),
}
_DATA = {
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
}
_TEXT = [
    "txt",
    "md",
    "rst",
    "log",
    "ini",
    "cfg",
    "conf",
    "toml",
    "yaml",
    "yml",
    "xml",
    "html",
    "htm",
    "css",
    "js",
    "mjs",
    "ts",
    "tsx",
    "jsx",
    "py",
    "sh",
    "sql",
    "rs",
    "go",
    "java",
    "c",
    "h",
    "cpp",
    "hpp",
    "rb",
    "php",
    "lua",
    "kt",
    "swift",
    "tex",
    "env",
    "diff",
    "patch",
]
_DANGEROUS = frozenset(
    [
        "exe",
        "dll",
        "bat",
        "cmd",
        "com",
        "scr",
        "msi",
        "so",
        "jar",
        "app",
        "vbs",
        "ps1",
        "php",
        "php3",
        "php5",
        "phtml",
        "jsp",
        "asp",
        "aspx",
        "cgi",
        "svg",
        "svgz",
        "swf",
        "lnk",
        "apk",
        "dmg",
        "iso",
        "zip",
        "tar",
        "gz",
        "7z",
        "rar",
    ]
)
_BINARY_MAGICS = (b"MZ", b"\x7fELF", b"PK\x03\x04", b"\xca\xfe\xba\xbe", b"%PDF-")
_SNIFF = 8192
_DOCX, _XLSX = "word/document.xml", "xl/workbook.xml"


@dataclass(frozen=True)
class Sniffed:
    ext: str
    mime: str
    kind: Kind
    width: int | None = None
    height: int | None = None


def ext_of(name: str) -> str:
    return name.rsplit(".", 1)[1].lower() if "." in name else ""


def clean_name(raw: str) -> str:
    """Safe display and storage name: no path, no control chars, bounded length."""
    name = unicodedata.normalize("NFC", raw or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = re.sub(r"[^\w .()+\-]", "_", name).strip(" .")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = stem.strip(" .")[:90] or "file"
    return f"{stem}.{ext[:12]}" if ext else stem


def _image_size(ext: str, head: bytes) -> tuple[int | None, int | None]:
    try:
        if ext == "png" and len(head) >= 24:  # noqa: PLR2004
            return struct.unpack(">II", head[16:24])
        if ext == "gif" and len(head) >= 10:  # noqa: PLR2004
            return struct.unpack("<HH", head[6:10])
        if ext == "webp" and head[8:12] == b"WEBP":
            return _webp_size(head)
        if ext in ("jpg", "jpeg"):
            return _jpeg_size(head)
    except (struct.error, IndexError):
        return None, None
    return None, None


def _webp_size(head: bytes) -> tuple[int | None, int | None]:
    kind = head[12:16]
    if kind == b"VP8X":
        w = int.from_bytes(head[24:27], "little") + 1
        h = int.from_bytes(head[27:30], "little") + 1
        return w, h
    if kind == b"VP8 ":
        w, h = struct.unpack("<HH", head[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(head[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None, None


def _jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:  # noqa: PLR2004
            i += 1
            continue
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):  # noqa: PLR2004
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2 : i + 4])[0]
    return None, None


def _is_text(head: bytes) -> bool:
    if b"\x00" in head or head.startswith(_BINARY_MAGICS):
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        return exc.start >= len(head) - 4  # a cut multi-byte char at the window end
    return True


def _zip_has(data: bytes, member: str) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(data)) as z:
            return member in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def sniff(name: str, data: bytes) -> Sniffed:  # noqa: C901
    """Classify an upload or raise DomainException (4101 type, 4104 mismatch, 4113)."""
    if not data:
        raise DomainException(EMPTY)
    parts = [p.lower() for p in name.split(".")[1:]]
    ext = ext_of(name)
    if not ext or any(p in _DANGEROUS for p in parts):
        raise DomainException(UNSUPPORTED)
    head = data[:_SNIFF]
    if ext in _IMAGES:
        mime, magic = _IMAGES[ext]
        if not head.startswith(magic) or (ext == "webp" and head[8:12] != b"WEBP"):
            raise DomainException(MISMATCH)
        w, h = _image_size(ext, data[:65536] if ext in ("jpg", "jpeg") else head)
        return Sniffed(ext, mime, "image", w, h)
    if ext == "pdf":
        if not head.startswith(b"%PDF-"):
            raise DomainException(MISMATCH)
        return Sniffed(ext, "application/pdf", "document")
    if ext in ("docx", "xlsx"):
        member = _DOCX if ext == "docx" else _XLSX
        if not head.startswith(b"PK\x03\x04") or not _zip_has(data, member):
            raise DomainException(MISMATCH)
        mime = "application/vnd.openxmlformats-officedocument." + (
            "wordprocessingml.document" if ext == "docx" else "spreadsheetml.sheet"
        )
        return Sniffed(ext, mime, "document" if ext == "docx" else "data")
    if ext in _DATA or ext in _TEXT:
        if len(data) < 1 or not _is_text(head):
            raise DomainException(MISMATCH)
        if ext in _DATA:
            return Sniffed(ext, _DATA[ext], "data")
        return Sniffed(ext, "text/plain", "text")
    raise DomainException(UNSUPPORTED)
