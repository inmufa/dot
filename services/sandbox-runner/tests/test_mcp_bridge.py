import asyncio
import os
import sys
import time

import httpx
import pytest
from dot_sandbox.main import create_app
from dot_sandbox.runtime import mcp_bridge
from dot_sandbox.settings import Settings

ECHO = "import sys\nfor l in sys.stdin:\n    print('echo:' + l.strip(), flush=True)\n"


async def post(c: httpx.AsyncClient, url: str, **body) -> httpx.Response:
    return await c.post(url, json=body)


async def spawn(c: httpx.AsyncClient, code: str = ECHO, **extra) -> str:
    r = await post(
        c, "/internal/mcp/spawn", command=sys.executable, args=["-c", code], **extra
    )
    assert r.status_code == 200, r.text
    return r.json()["proc_id"]


async def test_spawn_send_recv_close(client):
    pid = await spawn(client)
    await post(client, f"/internal/mcp/{pid}/send", line="hi")
    r = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=5)
    assert r.json()["lines"] == ["echo:hi"]
    assert r.json()["alive"] is True
    await post(client, f"/internal/mcp/{pid}/close")
    gone = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=0.1)
    assert gone.status_code == 404


async def test_recv_times_out_empty(client):
    pid = await spawn(client)
    r = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=0.2)
    assert r.json() == {"lines": [], "alive": True, "stderr": ""}
    await post(client, f"/internal/mcp/{pid}/close")


async def test_exit_is_reported(client):
    pid = await spawn(client, "import sys; print('bye'); sys.stderr.write('oops')")
    r = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=5)
    assert r.json()["lines"] == ["bye"]
    r = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=5)
    assert r.json()["alive"] is False
    await post(client, f"/internal/mcp/{pid}/close")


async def test_env_is_scrubbed_plus_explicit(client, secret_env):
    code = "import os; print(os.environ.get('FOO_TOKEN'), os.environ.get('MINE'))"
    pid = await spawn(client, code, env={"MINE": "ok"})
    r = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=5)
    assert r.json()["lines"] == ["None ok"]
    await post(client, f"/internal/mcp/{pid}/close")


@pytest.mark.parametrize("key", ["LD_PRELOAD", "1BAD", "A B", "BASH_ENV"])
async def test_dangerous_env_refused(client, key):
    r = await post(
        client,
        "/internal/mcp/spawn",
        command=sys.executable,
        args=["-c", "pass"],
        env={key: "x"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "bad_env"


async def test_cwd_is_jailed(client, ws):
    r = await post(
        client,
        "/internal/mcp/spawn",
        command=sys.executable,
        args=["-c", "pass"],
        cwd="/",
    )
    assert r.status_code == 403
    (ws / "sub").mkdir()
    pid = await spawn(client, "import os; print(os.getcwd())", cwd="sub")
    r = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=5)
    assert r.json()["lines"] == [str(ws / "sub")]
    await post(client, f"/internal/mcp/{pid}/close")


async def test_unknown_command_and_count_limit(client):
    r = await post(client, "/internal/mcp/spawn", command="no-such-binary-xyz")
    assert r.status_code == 404
    ids = [await spawn(client) for _ in range(8)]
    r = await post(
        client, "/internal/mcp/spawn", command=sys.executable, args=["-c", ECHO]
    )
    assert r.status_code == 429
    for pid in ids:
        await post(client, f"/internal/mcp/{pid}/close")


async def test_close_kills_the_whole_group(client, ws):
    marker = ws / "child.pid"
    code = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen(['sleep', '60']); open({str(marker)!r}, 'w')"
        ".write(str(p.pid)); print('up', flush=True); time.sleep(60)"
    )
    pid = await spawn(client, code)
    await post(client, f"/internal/mcp/{pid}/recv", timeout_s=5)
    child = int(marker.read_text())
    await post(client, f"/internal/mcp/{pid}/close")
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.05)
    pytest.fail("child process survived the group kill")


async def test_token_required(ws):
    app = create_app(Settings(workspace=ws, token="s3cret"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as c:
        r = await c.post("/internal/mcp/spawn", json={"command": "sh"})
        assert r.status_code == 401


async def test_other_session_cannot_touch_a_process(client):
    r = await client.post(
        "/internal/mcp/spawn",
        json={"command": sys.executable, "args": ["-c", ECHO]},
        headers={"X-Session-Id": "owner"},
    )
    pid = r.json()["proc_id"]
    for op, body in (("send", {"line": "x"}), ("recv", {"timeout_s": 0.1})):
        other = await client.post(
            f"/internal/mcp/{pid}/{op}", json=body, headers={"X-Session-Id": "other"}
        )
        assert other.status_code == 404
    await client.post(
        f"/internal/mcp/{pid}/close", json={}, headers={"X-Session-Id": "other"}
    )
    ok = await client.post(
        f"/internal/mcp/{pid}/recv",
        json={"timeout_s": 0.1},
        headers={"X-Session-Id": "owner"},
    )
    assert ok.status_code == 200  # a foreign close did nothing
    await client.post(
        f"/internal/mcp/{pid}/close", json={}, headers={"X-Session-Id": "owner"}
    )


async def test_idle_process_is_reaped_when_the_backend_vanishes(client, monkeypatch):
    pid = await spawn(client)
    monkeypatch.setattr(mcp_bridge, "IDLE_S", 0.0)
    await asyncio.sleep(0.05)
    second = await spawn(client)  # any spawn sweeps
    gone = await post(client, f"/internal/mcp/{pid}/recv", timeout_s=0.1)
    assert gone.status_code == 404
    await post(client, f"/internal/mcp/{second}/close")


async def test_concurrent_spawns_respect_the_cap(ws):
    app = create_app(Settings(workspace=ws, max_mcp_servers=2))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as c:
        rs = await asyncio.gather(*(spawn_raw(c) for _ in range(6)))
        codes = sorted(r.status_code for r in rs)
        assert codes.count(200) == 2
        for r in rs:
            if r.status_code == 200:
                await post(c, f"/internal/mcp/{r.json()['proc_id']}/close")
    await app.state.mcp.shutdown()


async def spawn_raw(c):
    return await post(
        c, "/internal/mcp/spawn", command=sys.executable, args=["-c", ECHO]
    )
