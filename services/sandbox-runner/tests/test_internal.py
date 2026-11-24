import httpx


async def post(c: httpx.AsyncClient, url: str, **body):
    return await c.post(url, json=body)


async def test_realpath_follows_symlink_inside(client, ws):
    (ws / "real.txt").write_text("x")
    (ws / "link").symlink_to(ws / "real.txt")
    b = (await post(client, "/internal/realpath", path="link")).json()
    assert b == {"path": str(ws / "real.txt"), "inside": True}


async def test_realpath_flags_escape(client, ws, tmp_path):
    outside = tmp_path / "out.txt"
    outside.write_text("x")
    (ws / "link").symlink_to(outside)
    b = (await post(client, "/internal/realpath", path="link")).json()
    assert b["inside"] is False


async def test_binaries_reports_only_existing_valid_names(client):
    r = await post(
        client, "/internal/binaries", names=["sh", "no-such-bin-xyz", "../sh"]
    )
    assert r.json() == {"found": ["sh"]}
