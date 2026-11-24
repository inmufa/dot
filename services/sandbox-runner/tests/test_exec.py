import asyncio
import os
import time
from pathlib import Path

import httpx


async def ex(c: httpx.AsyncClient, url="/exec", sid="s1", **body):
    return await c.post(url, json=body, headers={"X-Session-Id": sid})


async def test_exit_codes_and_streams(client, ws):
    r = await ex(client, command="echo out; echo err >&2; exit 3")
    b = r.json()
    assert (b["stdout"], b["stderr"], b["exit_code"]) == ("out\n", "err\n", 3)
    assert b["timed_out"] is False
    assert b["truncated"] is False
    assert b["spill_path"] is None
    assert b["shell_id"] is None
    assert (await ex(client, command="true")).json()["exit_code"] == 0


async def test_cwd(client, ws):
    (ws / "d").mkdir()
    r = await ex(client, command="pwd", cwd=str(ws / "d"))
    assert r.json()["stdout"].strip() == str(ws / "d")
    assert (await ex(client, command="pwd", cwd=str(ws / "none"))).status_code == 404


async def test_timeout_kills_group(client, ws):
    marker = ws / "alive"
    cmd = f"(sleep 1.5; touch {marker}) & sleep 30"
    t0 = time.monotonic()
    r = await ex(client, command=cmd, timeout_s=0.5)
    assert time.monotonic() - t0 < 5
    b = r.json()
    assert b["timed_out"] is True
    assert b["exit_code"] != 0
    await asyncio.sleep(2)
    assert not marker.exists()


async def test_output_spill(client, ws):
    r = await ex(
        client,
        command="python3 -c \"print('x' * 100000)\" || head -c 100000 /dev/zero | tr '\\0' x",
    )
    b = r.json()
    assert b["truncated"] is True
    assert len(b["stdout"]) < 31000
    assert "truncated" in b["stdout"]
    spill = Path(b["spill_path"])
    assert spill.parent == ws / ".dot" / "tool_outputs"
    text = spill.read_text()  # noqa: ASYNC240
    assert text.count("x") >= 100000


async def test_background_output_and_kill(client, ws):
    r = await ex(client, command="echo started; sleep 60", background=True)
    sid = r.json()["shell_id"]
    assert sid
    for _ in range(50):
        o = (await ex(client, "/exec/output", shell_id=sid)).json()
        if "started" in o["stdout"]:
            break
        await asyncio.sleep(0.1)
    assert o["running"] is True
    assert o["exit_code"] is None
    assert "started" in o["stdout"]
    assert (await ex(client, "/exec/kill", shell_id=sid)).json() == {"ok": True}
    o = (await ex(client, "/exec/output", shell_id=sid)).json()
    assert o["running"] is False
    assert o["exit_code"] != 0
    # other session cannot see it
    assert (await ex(client, "/exec/output", sid="zz", shell_id=sid)).status_code == 404
    assert (await ex(client, "/exec/kill", shell_id="sh_nope")).status_code == 404


async def test_background_finishes(client):
    sid = (await ex(client, command="echo done; exit 2", background=True)).json()[
        "shell_id"
    ]
    for _ in range(50):
        o = (await ex(client, "/exec/output", shell_id=sid)).json()
        if not o["running"]:
            break
        await asyncio.sleep(0.1)
    assert (o["stdout"], o["exit_code"]) == ("done\n", 2)


async def test_env_scrubbed(client, secret_env):
    r = await ex(client, command="env")
    out = r.json()["stdout"]
    assert "FOO_TOKEN" not in out
    assert "DOT_" not in out
    assert "hunter2" not in out
    assert "PATH=" in out
    assert os.environ["FOO_TOKEN"] == "abc"
