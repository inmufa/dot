import io
import zipfile

import httpx
from docs_fixtures import docx, pdf, xlsx


async def put(c: httpx.AsyncClient, path: str, data: bytes) -> httpx.Response:
    return await c.post("/internal/write_binary", params={"path": path}, content=data)


async def test_write_binary_creates_file_under_uploads(client, ws):
    r = await put(client, str(ws / "uploads/s1/a.bin"), b"\x00\x01data")
    assert r.status_code == 200
    assert (ws / "uploads/s1/a.bin").read_bytes() == b"\x00\x01data"
    assert r.json()["size"] == 6


async def test_write_binary_refuses_overwrite_and_outside_uploads(client, ws):
    assert (await put(client, "uploads/s1/a.bin", b"x")).status_code == 200
    assert (await put(client, "uploads/s1/a.bin", b"y")).status_code == 409
    assert (await put(client, "notes.txt", b"y")).status_code == 403
    assert (await put(client, ".dot/x", b"y")).status_code == 403
    assert (await put(client, "uploads/../../etc/x", b"y")).status_code == 403
    assert (await put(client, "uploads", b"y")).status_code == 403


async def test_write_binary_symlink_escape(client, ws, tmp_path):
    (ws / "uploads").mkdir()
    outside = tmp_path / "out"
    outside.mkdir()
    (ws / "uploads" / "evil").symlink_to(outside)
    r = await put(client, "uploads/evil/x.bin", b"y")
    assert r.status_code == 403
    assert not (outside / "x.bin").exists()


async def test_write_binary_size_cap(app_settings_client, ws):
    c = app_settings_client
    r = await put(c, "uploads/s1/big.bin", b"x" * 300)
    assert r.status_code == 413
    assert not (ws / "uploads/s1/big.bin").exists()


async def test_extract_docx_xlsx_pdf(client, ws):
    (ws / "d.docx").write_bytes(docx("Hello <b>", "second"))
    (ws / "x.xlsx").write_bytes(xlsx([["a", "b"], ["1", "2"]]))
    (ws / "p.pdf").write_bytes(pdf("Hello pdf"))
    for name, kind, want in (
        ("d.docx", "docx", "Hello"),
        ("x.xlsx", "xlsx", "a\tb"),
        ("p.pdf", "pdf", "Hello pdf"),
    ):
        r = await client.post("/internal/extract", json={"path": name, "kind": kind})
        assert r.status_code == 200, r.text
        assert want in r.json()["text"]


async def test_extract_rejects_bad_inputs(client, ws):
    (ws / "bad.docx").write_bytes(b"not a zip")
    bomb = zipfile.ZipFile(io.BytesIO(), "w")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"A" * 50_000_000)
    (ws / "bomb.docx").write_bytes(buf.getvalue())
    xxe = docx("x").replace(b"x</w:t>", b"x</w:t>")
    (ws / "dtd.docx").write_bytes(
        __import__("docs_fixtures").zipped(
            {"word/document.xml": '<!DOCTYPE a [<!ENTITY e "boom">]><a>&e;</a>'}
        )
    )
    (ws / "junk.pdf").write_bytes(b"%PDF-1.4 garbage")
    assert xxe
    assert bomb
    for name, kind in (
        ("bad.docx", "docx"),
        ("bomb.docx", "docx"),
        ("dtd.docx", "docx"),
        ("junk.pdf", "pdf"),
    ):
        r = await client.post("/internal/extract", json={"path": name, "kind": kind})
        assert r.status_code == 422, (name, r.text)
        assert r.json()["error"] == "extract_failed"
    r = await client.post("/internal/extract", json={"path": "../x", "kind": "pdf"})
    assert r.status_code == 403
    r = await client.post("/internal/extract", json={"path": "bad.docx", "kind": "exe"})
    assert r.status_code == 422


async def test_raw_cap_hidden_and_escape(client, ws, tmp_path):
    (ws / "a.txt").write_text("hello")
    (ws / "big.txt").write_text("x" * 100)
    (ws / ".dot").mkdir()
    (ws / ".dot/secret").write_text("s")
    (tmp_path / "out.txt").write_text("outside")
    (ws / "link").symlink_to(tmp_path / "out.txt")
    ok = await client.get("/internal/raw", params={"path": "a.txt"})
    assert ok.content == b"hello"
    big = await client.get("/internal/raw", params={"path": "big.txt", "max_bytes": 10})
    assert big.status_code == 413
    assert (
        await client.get("/internal/raw", params={"path": ".dot/secret"})
    ).status_code == 404
    assert (
        await client.get("/internal/raw", params={"path": "link"})
    ).status_code == 403
    assert (
        await client.get("/internal/raw", params={"path": "nope"})
    ).status_code == 404


async def test_tree_hides_dot_and_escaping_links(client, ws, tmp_path):
    (ws / "src").mkdir()
    (ws / "src/m.py").write_text("x")
    (ws / ".dot").mkdir()
    (ws / "top.txt").write_text("t")
    (tmp_path / "o").mkdir()
    (ws / "esc").symlink_to(tmp_path / "o")
    r = await client.post("/internal/tree", json={"depth": 2})
    names = [e["name"] for e in r.json()["entries"]]
    assert "src" in names
    assert "m.py" in names
    assert ".dot" not in names
    assert "esc" not in names
    r = await client.post("/internal/tree", json={"path": ".dot"})
    assert r.status_code == 404


async def test_recent_and_stat(client, ws):
    (ws / "a.csv").write_text("a")
    (ws / ".dot").mkdir()
    (ws / ".dot/x").write_text("x")
    r = await client.post("/internal/recent", json={"since": 0})
    names = [e["name"] for e in r.json()["entries"]]
    assert names == ["a.csv"]
    r = await client.post(
        "/internal/stat", json={"paths": ["a.csv", "../etc/passwd", ".dot/x"]}
    )
    assert [e["name"] for e in r.json()["entries"]] == ["a.csv"]


async def test_delete_upload_only_inside_uploads(client, ws):
    await put(client, "uploads/s1/a.bin", b"x")
    (ws / "keep.txt").write_text("k")
    r = await client.post("/internal/delete_upload", json={"path": "uploads/s1/a.bin"})
    assert r.json() == {"deleted": True}
    assert not (ws / "uploads/s1/a.bin").exists()
    r = await client.post("/internal/delete_upload", json={"path": "keep.txt"})
    assert r.status_code == 403
    assert (ws / "keep.txt").exists()
