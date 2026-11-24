import os
from pathlib import Path

import httpx
from dot_sandbox.main import create_app
from dot_sandbox.settings import Settings


async def post(c: httpx.AsyncClient, url: str, sid: str = "s1", **body):
    return await c.post(url, json=body, headers={"X-Session-Id": sid})


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_jail_dotdot(client, ws):
    r = await post(client, "/fs/read", path=f"{ws}/../etc/passwd")
    assert r.status_code == 403
    assert r.json()["error"] == "outside_workspace"
    r = await post(client, "/fs/write", path="/etc/evil", content="x")
    assert r.status_code == 403


async def test_jail_symlink(client, ws, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("top")
    (ws / "link").symlink_to(outside)
    (ws / "dirlink").symlink_to(tmp_path)
    assert (await post(client, "/fs/read", path=str(ws / "link"))).status_code == 403
    r = await post(
        client, "/fs/write", path=str(ws / "dirlink" / "new.txt"), content="x"
    )
    assert r.status_code == 403
    assert not (tmp_path / "new.txt").exists()
    r = await post(client, "/exec", command="true", cwd=str(ws / "dirlink"))
    assert r.status_code == 403


async def test_symlink_inside_ok(client, ws):
    (ws / "a.txt").write_text("hi\n")
    (ws / "ln").symlink_to(ws / "a.txt")
    r = await post(client, "/fs/read", path=str(ws / "ln"))
    assert r.status_code == 200


async def test_read_numbering_offset_limit(client, ws):
    (ws / "f.txt").write_text("\n".join(f"l{i}" for i in range(1, 11)) + "\n")
    r = await post(client, "/fs/read", path=str(ws / "f.txt"))
    body = r.json()
    assert body["total_lines"] == 10
    assert body["numbered"] is True
    assert body["content"].splitlines()[0] == "     1\tl1"
    r = await post(client, "/fs/read", path=str(ws / "f.txt"), offset=3, limit=2)
    assert r.json()["content"] == "     4\tl4\n     5\tl5"
    assert r.json()["total_lines"] == 10


async def test_read_missing_and_dir(client, ws):
    assert (await post(client, "/fs/read", path=str(ws / "no"))).status_code == 404
    assert (await post(client, "/fs/read", path=str(ws))).status_code == 400


async def test_write_new_then_overwrite_requires_read(client, ws):
    p = str(ws / "sub" / "n.txt")
    r = await post(client, "/fs/write", path=p, content="one")
    assert r.json() == {"path": p, "created": True}
    # writer of the file may overwrite in same session
    assert (await post(client, "/fs/write", path=p, content="two")).json()[
        "created"
    ] is False
    # other session never read it
    r = await post(client, "/fs/write", sid="other", path=p, content="x")
    assert r.status_code == 409
    assert r.json()["error"] == "read_required"
    await post(client, "/fs/read", sid="other", path=p)
    assert (
        await post(client, "/fs/write", sid="other", path=p, content="x")
    ).status_code == 200


async def test_edit_requires_read_and_detects_change(client, ws):
    p = ws / "e.txt"
    p.write_text("hello world\n")
    r = await post(client, "/fs/edit", path=str(p), old="hello", new="bye")
    assert r.status_code == 409
    await post(client, "/fs/read", path=str(p))
    r = await post(client, "/fs/edit", path=str(p), old="hello", new="bye")
    assert r.json()["replacements"] == 1
    assert p.read_text() == "bye world\n"
    # changed on disk after read
    p.write_text("changed externally!\n")
    os.utime(p, ns=(1, 1))
    r = await post(client, "/fs/edit", path=str(p), old="changed", new="x")
    assert r.status_code == 409
    assert "changed" in r.json()["detail"]
    r = await post(client, "/fs/write", path=str(p), content="x")
    assert r.status_code == 409


async def test_edit_no_match_ambiguous_replace_all(client, ws):
    p = ws / "m.txt"
    p.write_text("a b a b a\n")
    await post(client, "/fs/read", path=str(p))
    r = await post(client, "/fs/edit", path=str(p), old="zzz", new="y")
    assert (r.status_code, r.json()["error"]) == (422, "no_match")
    r = await post(client, "/fs/edit", path=str(p), old="a", new="y")
    assert (r.status_code, r.json()["error"]) == (422, "ambiguous")
    r = await post(client, "/fs/edit", path=str(p), old="a", new="y", replace_all=True)
    assert r.json()["replacements"] == 3
    assert p.read_text() == "y b y b y\n"


async def test_edit_lint_shell(client, ws):
    p = ws / "s.sh"
    p.write_text("echo ok\n")
    await post(client, "/fs/read", path=str(p))
    r = await post(client, "/fs/edit", path=str(p), old="echo ok", new="if then")
    assert r.status_code == 200
    assert r.json()["lint"]
    r = await post(client, "/fs/edit", path=str(p), old="if then", new="echo fine")
    assert r.json()["lint"] is None


async def test_glob_ordering_and_limit(client, ws):
    for i, name in enumerate(["old.py", "mid.py", "new.py"]):
        f = ws / "src" / name
        f.parent.mkdir(exist_ok=True)
        f.write_text("x")
        os.utime(f, ns=((i + 1) * 10**9, (i + 1) * 10**9))
    (ws / "src" / "skip.txt").write_text("x")
    r = await post(client, "/fs/glob", pattern="**/*.py")
    names = [Path(p).name for p in r.json()["paths"]]
    assert names == ["new.py", "mid.py", "old.py"]
    r = await post(client, "/fs/glob", pattern="*.py", path=str(ws / "src"))
    assert len(r.json()["paths"]) == 3
    assert (await post(client, "/fs/glob", pattern="../*")).status_code == 400


async def test_glob_max_500(client, ws):
    for i in range(510):
        (ws / f"f{i}.dat").write_text("x")
    r = await post(client, "/fs/glob", pattern="*.dat")
    assert len(r.json()["paths"]) == 500


async def test_grep_modes(client, ws):
    (ws / "a.py").write_text("alpha\nbeta\nAlpha two\ngamma\n")
    (ws / "b.txt").write_text("nothing\nalpha\n")
    a, b = str(ws / "a.py"), str(ws / "b.txt")
    r = await post(client, "/fs/grep", pattern="alpha")
    assert r.json()["output"].splitlines() == [a, b]
    r = await post(
        client, "/fs/grep", pattern="alpha", ignore_case=True, output_mode="count"
    )
    assert r.json()["output"].splitlines() == [f"{a}:2", f"{b}:1"]
    r = await post(client, "/fs/grep", pattern="beta", output_mode="content", context=1)
    assert r.json()["output"].splitlines() == [
        f"{a}-1-alpha",
        f"{a}:2:beta",
        f"{a}-3-Alpha two",
    ]
    r = await post(client, "/fs/grep", pattern="alpha", glob="*.py")
    assert r.json()["output"] == a
    r = await post(
        client, "/fs/grep", pattern="alpha", output_mode="content", head_limit=1
    )
    assert len(r.json()["output"].splitlines()) == 1
    assert (await post(client, "/fs/grep", pattern="(")).status_code == 422
    assert (
        await post(client, "/fs/grep", pattern="a", output_mode="x")
    ).status_code == 422


async def test_token(ws):
    app = create_app(Settings(workspace=ws, token="tok"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as c:
        assert (await c.get("/health")).status_code == 200
        r = await c.post("/fs/glob", json={"pattern": "*"})
        assert r.status_code == 401
        r = await c.post(
            "/fs/glob", json={"pattern": "*"}, headers={"X-Sandbox-Token": "tok"}
        )
        assert r.status_code == 200
    await app.state.shells.shutdown()
