# ruff: noqa: EM101, EM102, S314, TRY301, PLC0415, PLR2004
"""Text extraction for pdf/docx/xlsx. Runs as a subprocess (`python -m dot_sandbox.runtime.extract`).

Untrusted input: caps on pages, rows and characters, zip-bomb guards, no DTDs.
"""

import json
import re
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_CHARS = 200_000
MAX_PDF_PAGES = 200
MAX_ZIP_MEMBERS = 2000
MAX_ZIP_TOTAL = 150_000_000  # declared uncompressed bytes
MAX_ZIP_RATIO = 200
MAX_XML_BYTES = 40_000_000
MAX_SHEETS = 20
MAX_ROWS = 2000
MAX_COLS = 60
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DTD = re.compile(rb"<!(DOCTYPE|ENTITY)", re.IGNORECASE)


class ExtractError(Exception):
    """The file cannot be read safely."""


def _open_zip(path: Path) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ExtractError("not a valid zip container") from exc
    infos = z.infolist()
    total = sum(i.file_size for i in infos)
    packed = max(1, sum(i.compress_size for i in infos))
    if len(infos) > MAX_ZIP_MEMBERS or total > MAX_ZIP_TOTAL:
        raise ExtractError("archive is too large")
    if total / packed > MAX_ZIP_RATIO:
        raise ExtractError("suspicious compression ratio")
    return z


def _xml_bytes(z: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = z.getinfo(name)
    except KeyError as exc:
        raise ExtractError(f"missing part {name}") from exc
    if info.file_size > MAX_XML_BYTES:
        raise ExtractError("part is too large")
    with z.open(info) as fh:
        data = fh.read(MAX_XML_BYTES + 1)  # real size, not the declared one
    if len(data) > MAX_XML_BYTES or _DTD.search(data[:4096]):
        raise ExtractError("unsafe xml")
    return data


def _iter_xml(z: zipfile.ZipFile, name: str) -> Iterator[ET.Element]:
    import io

    for _, el in ET.iterparse(io.BytesIO(_xml_bytes(z, name)), events=("end",)):
        yield el


def docx_text(path: Path) -> tuple[str, int | None]:
    z = _open_zip(path)
    paras: list[str] = []
    size = 0
    for el in _iter_xml(z, "word/document.xml"):
        if el.tag == f"{_W}p":
            line = "".join(
                (t.text or "")
                if t.tag == f"{_W}t"
                else ("\t" if t.tag == f"{_W}tab" else "")
                for t in el.iter()
            )
            paras.append(line)
            size += len(line) + 1
            el.clear()
            if size > MAX_CHARS:
                break
    return "\n".join(paras), None


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    out: list[str] = []
    for el in _iter_xml(z, "xl/sharedStrings.xml"):
        if el.tag == f"{_S}si":
            out.append("".join(t.text or "" for t in el.iter(f"{_S}t")))
            el.clear()
            if len(out) > 500_000:
                break
    return out


def _col_index(ref: str) -> int:
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def _sheet_rows(z: zipfile.ZipFile, name: str, strings: list[str]) -> list[str]:
    rows: list[str] = []
    for el in _iter_xml(z, name):
        if el.tag != f"{_S}row":
            continue
        cells: dict[int, str] = {}
        for c in el.iter(f"{_S}c"):
            v = c.find(f"{_S}v")
            text = v.text if v is not None and v.text else ""
            if c.get("t") == "s" and text.isdigit() and int(text) < len(strings):
                text = strings[int(text)]
            elif c.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{_S}t"))
            idx = _col_index(c.get("r", ""))
            if 0 <= idx < MAX_COLS:
                cells[idx] = text
        width = max(cells, default=-1) + 1
        rows.append("\t".join(cells.get(i, "") for i in range(width)))
        el.clear()
        if len(rows) >= MAX_ROWS:
            break
    return rows


def xlsx_text(path: Path) -> tuple[str, int | None]:
    z = _open_zip(path)
    strings = _shared_strings(z)
    sheets = sorted(
        (n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
        key=lambda n: int(re.findall(r"\d+", n)[0]),
    )[:MAX_SHEETS]
    parts = []
    for i, name in enumerate(sheets, 1):
        parts.append(f"## Sheet {i}\n" + "\n".join(_sheet_rows(z, name, strings)))
    return "\n\n".join(parts), len(sheets)


def pdf_text(path: Path) -> tuple[str, int | None]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ExtractError("encrypted pdf")
        total = len(reader.pages)
        out, size = [], 0
        for page in reader.pages[:MAX_PDF_PAGES]:
            text = page.extract_text() or ""
            out.append(text)
            size += len(text)
            if size > MAX_CHARS:
                break
    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError("pdf could not be parsed") from exc
    return "\n\n".join(out), total


EXTRACTORS = {"pdf": pdf_text, "docx": docx_text, "xlsx": xlsx_text}


def extract(path: Path, kind: str) -> dict[str, object]:
    fn = EXTRACTORS.get(kind)
    if fn is None:
        raise ExtractError("unsupported kind")
    text, pages = fn(path)
    text = text.replace("\x00", "")
    return {
        "text": text[:MAX_CHARS],
        "pages": pages,
        "truncated": len(text) > MAX_CHARS,
    }


def main(argv: list[str]) -> int:
    try:
        sys.stdout.write(json.dumps(extract(Path(argv[1]), argv[2])))
    except ExtractError as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
