import os

import httpx


async def post(c: httpx.AsyncClient, url: str, sid: str = "s1", **body):
    return await c.post(url, json=body, headers={"X-Session-Id": sid})


async def test_exec_stdin_reaches_command(client):
    r = await post(client, "/exec", command="cat", stdin="hello\nworld")
    b = r.json()
    assert (b["stdout"], b["exit_code"]) == ("hello\nworld", 0)


async def test_exec_without_stdin_still_closed(client):
    r = await post(client, "/exec", command="cat; echo done", timeout_s=5)
    assert r.json()["stdout"] == "done\n"


async def test_exec_stdin_ignored_by_command_is_fine(client):
    r = await post(client, "/exec", command="true", stdin="x" * 500_000)
    assert r.json()["exit_code"] == 0


async def test_exec_stdin_background(client):
    r = await post(client, "/exec", command="cat", stdin="bg", background=True)
    sid = r.json()["shell_id"]
    out = {}
    for _ in range(50):
        out = (await post(client, "/exec/output", shell_id=sid)).json()
        if not out["running"]:
            break
    assert out["stdout"] == "bg"


async def test_checkpoint_saves_and_restores_content(client, ws):
    f = ws / "a.txt"
    f.write_text("v1")
    r = await post(client, "/internal/checkpoint", path=str(f))
    assert r.json() == {"checkpoint_id": "1", "existed": True}
    stored = ws / ".dot" / "checkpoints" / "s1" / "1"
    assert (stored / "content").read_text() == "v1"
    f.write_text("v2")
    r = await post(client, "/internal/restore", checkpoint_id="1")
    assert r.json() == {"path": str(f), "action": "restored"}
    assert f.read_text() == "v1"


async def test_checkpoint_of_missing_file_restores_by_deleting(client, ws):
    f = ws / "new" / "b.txt"
    r = await post(client, "/internal/checkpoint", path=str(f))
    assert r.json()["existed"] is False
    f.parent.mkdir()
    f.write_text("created later")
    r = await post(client, "/internal/restore", checkpoint_id=r.json()["checkpoint_id"])
    assert r.json()["action"] == "deleted"
    assert not f.exists()


async def test_checkpoint_ids_increase_per_session(client, ws):
    (ws / "a").write_text("x")
    ids = [
        (await post(client, "/internal/checkpoint", sid=s, path=str(ws / "a"))).json()[
            "checkpoint_id"
        ]
        for s in ("s1", "s1", "s2")
    ]
    assert ids == ["1", "2", "1"]


async def test_checkpoint_jail_and_protected_path(client, ws):
    r = await post(client, "/internal/checkpoint", path="/etc/passwd")
    assert r.status_code == 403
    r = await post(client, "/internal/checkpoint", path=str(ws / ".dot" / "x"))
    assert r.json()["error"] == "protected_path"
    r = await post(client, "/internal/checkpoint", sid="../evil", path=str(ws / "a"))
    assert r.json()["error"] == "invalid_session"
    r = await post(client, "/internal/restore", checkpoint_id="7")
    assert r.status_code == 404
    r = await post(client, "/internal/restore", checkpoint_id="../1")
    assert r.status_code == 400


async def test_restore_cannot_be_pointed_outside_workspace(client, ws, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("safe")
    meta = ws / ".dot" / "checkpoints" / "s1" / "1"
    meta.mkdir(parents=True)
    (meta / "meta.json").write_text(f'{{"path": "{victim}", "existed": false}}')
    r = await post(client, "/internal/restore", checkpoint_id="1")
    assert r.status_code == 403
    assert victim.read_text() == "safe"


async def test_checkpoint_keeps_file_mode_on_restore(client, ws):
    f = ws / "run.sh"
    f.write_text("echo 1")
    f.chmod(0o755)
    await post(client, "/internal/checkpoint", path=str(f))
    f.write_text("echo 2")
    await post(client, "/internal/restore", checkpoint_id="1")
    assert f.read_text() == "echo 1"
    assert os.access(f, os.X_OK)


async def test_peek_does_not_mark_file_as_read(client, ws):
    f = ws / "p.txt"
    f.write_text("current")
    r = await post(client, "/internal/peek", path=str(f))
    assert r.json() == {"exists": True, "content": "current"}
    r = await post(client, "/fs/write", path=str(f), content="new")
    assert r.status_code == 409  # still needs a Read
    r = await post(client, "/internal/peek", path=str(ws / "none"))
    assert r.json() == {"exists": False, "content": None}
    assert (await post(client, "/internal/peek", path="/etc/passwd")).status_code == 403


async def test_peek_refuses_symlinks_and_dotdot_that_leave_the_workspace(
    client, ws, tmp_path
):
    secret = tmp_path / "secret.md"
    secret.write_text("outside")
    (ws / "DOT.md").symlink_to(secret)
    assert (
        await post(client, "/internal/peek", path=str(ws / "DOT.md"))
    ).status_code == 403
    r = await post(client, "/internal/peek", path=str(ws / ".." / "secret.md"))
    assert r.status_code == 403


async def test_restore_dry_run_changes_nothing_and_flags_missing(client, ws):
    f = ws / "a.txt"
    f.write_text("v1")
    cp = (await post(client, "/internal/checkpoint", path=str(f))).json()
    f.write_text("v2")
    ok = await post(
        client, "/internal/restore", checkpoint_id=cp["checkpoint_id"], dry_run=True
    )
    assert ok.status_code == 200
    assert f.read_text() == "v2"
    gone = await post(client, "/internal/restore", checkpoint_id="99", dry_run=True)
    assert gone.status_code == 404
