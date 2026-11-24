import asyncio
import contextlib
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dot_sandbox import search
from dot_sandbox.main import create_app
from dot_sandbox.settings import Settings
from dot_sandbox.shell import FSIZE_KB, ShellManager


async def post(c: httpx.AsyncClient, url: str, sid: str = "s1", **body):
    return await c.post(url, json=body, headers={"X-Session-Id": sid})


async def test_fifo_read_is_refused_not_blocked(client, ws):
    fifo = ws / "pipe"
    os.mkfifo(fifo)
    r = await post(client, "/fs/read", path=str(fifo))
    assert r.status_code == 400
    assert r.json()["error"] == "not_regular"


async def test_dot_dir_is_protected_from_fs_writes(client, ws):
    d = ws / ".dot" / "tool_outputs"
    d.mkdir(parents=True)
    (d / "a.log").write_text("log")
    r = await post(client, "/fs/write", path=str(d / "new.log"), content="x")
    assert r.status_code == 403
    assert r.json()["error"] == "protected_path"
    await post(client, "/fs/read", path=str(d / "a.log"))
    r = await post(client, "/fs/edit", path=str(d / "a.log"), old="log", new="evil")
    assert r.status_code == 403
    assert (d / "a.log").read_text() == "log"


async def test_write_size_cap(ws):
    app = create_app(Settings(workspace=ws, max_read_bytes=10))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as c:
        r = await post(c, "/fs/write", path=str(ws / "big"), content="x" * 11)
    assert r.status_code == 413
    await app.state.shells.shutdown()


async def test_background_child_does_not_outlive_foreground_command(client, ws):
    pidfile = ws / "pid"
    r = await post(client, "/exec", command=f"sleep 300 & echo $! > {pidfile}")
    assert r.json()["exit_code"] == 0
    pid = int(pidfile.read_text())
    for _ in range(50):
        try:
            stat = await asyncio.to_thread(Path(f"/proc/{pid}/stat").read_text)
            state = stat.split(")")[1].split()[0]
        except (FileNotFoundError, ProcessLookupError):
            return
        if state == "Z":  # killed, not yet reaped
            return
        await asyncio.sleep(0.1)
    msg = "background child survived"
    raise AssertionError(msg)


async def test_output_flood_is_capped_by_ulimit(client, ws):
    r = await post(client, "/exec", command="ulimit -f", timeout_s=10)
    assert r.json()["stdout"].strip() == str(search_ulimit())


def search_ulimit() -> int:
    return FSIZE_KB


async def test_scratch_files_removed_on_cancel(ws):
    sh = ShellManager(ws)
    task = asyncio.create_task(sh.run("s", "sleep 30", ws, 60))
    await asyncio.sleep(0.3)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert list(sh.scratch.iterdir()) == []
    await sh.shutdown()


async def test_cross_session_shell_ids_are_isolated(client, ws):
    r = await post(client, "/exec", sid="a", command="sleep 30", background=True)
    sid = r.json()["shell_id"]
    assert (
        await post(client, "/exec/output", sid="b", shell_id=sid)
    ).status_code == 404
    assert (await post(client, "/exec/kill", sid="b", shell_id=sid)).status_code == 404
    assert (await post(client, "/exec/kill", sid="a", shell_id=sid)).status_code == 200


async def test_grep_streams_and_respects_head_limit(client, ws):
    (ws / "big.txt").write_text("hit\n" * 50_000)
    r = await post(
        client, "/fs/grep", pattern="hit", output_mode="content", head_limit=3
    )
    assert len(r.json()["output"].splitlines()) == 3


async def test_python_grep_fallback_skips_huge_and_fifo(ws, monkeypatch):
    monkeypatch.setattr(search.shutil, "which", lambda _n: None)
    os.mkfifo(ws / "pipe")
    (ws / "huge.txt").write_text("needle" + "x" * (search.MAX_GREP_FILE + 1))
    (ws / "ok.txt").write_text("needle\n")
    out = await search.grep(ws, ws, search.GrepQuery("needle"))
    assert out.splitlines() == [str(ws / "ok.txt")]


def test_process_is_made_non_dumpable():
    code = (
        "import ctypes;from dot_sandbox.main import harden_process;"
        "harden_process();print(ctypes.CDLL(None).prctl(3,0,0,0,0))"
    )
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "0"
