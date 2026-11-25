"""Tiny office/pdf files built in memory."""

import io
import zipfile
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def zipped(parts: dict[str, bytes | str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return buf.getvalue()


def docx(*paras: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paras)
    xml = f'<?xml version="1.0"?><w:document {W}><w:body>{body}</w:body></w:document>'
    return zipped({"word/document.xml": xml})


def xlsx(rows: list[list[str]]) -> bytes:
    strings = [c for r in rows for c in r]
    sst = "".join(f"<si><t>{c}</t></si>" for c in strings)
    out, i = [], 0
    for ri, r in enumerate(rows, 1):
        cells = ""
        for ci, _ in enumerate(r):
            cells += f'<c r="{chr(65 + ci)}{ri}" t="s"><v>{i}</v></c>'
            i += 1
        out.append(f'<row r="{ri}">{cells}</row>')
    sheet = f"<worksheet {S}><sheetData>{''.join(out)}</sheetData></worksheet>"
    return zipped(
        {
            "xl/sharedStrings.xml": f"<sst {S}>{sst}</sst>",
            "xl/worksheets/sheet1.xml": sheet,
        }
    )


def pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        x,
    )
    return out
