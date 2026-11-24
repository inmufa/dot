import asyncio
import os
import time
from pathlib import Path

from dot_sandbox import checkpoints
from dot_sandbox.runtime import retention

DAY = 86_400


def make(root, session: str, n: int, size: int, age_days: float) -> None:
    d = root / ".dot" / "checkpoints" / session / str(n)
    d.mkdir(parents=True)
    (d / "content").write_bytes(b"x" * size)
    (d / "meta.json").write_text("{}")
    t = time.time() - age_days * DAY
    os.utime(d / "meta.json", (t, t))


def run(root, **kw):
    args = {"checkpoint_days": 14, "checkpoint_max_bytes": 10**9, "outputs_days": 7}
    return retention.prune(root, **{**args, **kw})


def left(root, session: str) -> list[str]:
    sdir = root / ".dot" / "checkpoints" / session
    return sorted(p.name for p in sdir.iterdir() if p.name.isdigit())


def test_old_checkpoints_are_removed(ws):
    make(ws, "s1", 1, 10, 30)
    make(ws, "s1", 2, 10, 1)
    rep = run(ws)
    assert left(ws, "s1") == ["2"]
    assert rep.checkpoints_removed == 1


def test_size_cap_drops_oldest_first(ws):
    for n in range(1, 5):
        make(ws, "s1", n, 1000, 1)
    run(ws, checkpoint_max_bytes=2100)
    assert left(ws, "s1") == ["3", "4"]


def test_sessions_are_independent_and_empty_dirs_go(ws):
    make(ws, "old", 1, 10, 99)
    make(ws, "new", 1, 10, 1)
    run(ws)
    assert left(ws, "new") == ["1"]
    sdir = ws / ".dot" / "checkpoints" / "old"
    assert not [p for p in sdir.iterdir() if p.name.isdigit()]


def test_pruned_ids_are_never_reused(ws):
    (ws / "f.txt").write_text("a")
    first, _ = checkpoints.save(ws, "s1", str(ws / "f.txt"), 10**6)
    sdir = ws / ".dot" / "checkpoints" / "s1"
    old = time.time() - 40 * DAY
    os.utime(sdir / first / "meta.json", (old, old))
    run(ws)
    second, _ = checkpoints.save(ws, "s1", str(ws / "f.txt"), 10**6)
    assert int(second) > int(first)


def test_spill_files_expire(ws):
    out = ws / ".dot" / "tool_outputs"
    out.mkdir(parents=True)
    old, fresh = out / "a.log", out / "b.log"
    old.write_text("x")
    fresh.write_text("y")
    t = time.time() - 20 * DAY
    os.utime(old, (t, t))
    rep = run(ws)
    assert not old.exists()
    assert fresh.exists()
    assert rep.outputs_removed == 1


def test_nothing_to_do_on_empty_workspace(ws):
    assert run(ws).checkpoints_removed == 0


async def test_endpoint_and_spill(client, ws):
    s = await client.post("/internal/spill", json={"content": "hello"})
    path = s.json()["path"]
    assert path.startswith(str(ws / ".dot" / "tool_outputs"))
    assert await asyncio.to_thread(Path(path).read_text) == "hello"
    r = await client.post("/internal/retention", json={})
    assert r.status_code == 200
    assert set(r.json()) == {"checkpoints_removed", "outputs_removed", "bytes_freed"}
    bad = await client.post("/internal/retention", json={"checkpoint_days": 0})
    assert bad.status_code == 422


def test_protected_sessions_keep_their_newest_checkpoints(ws):
    for n in range(1, 6):
        make(ws, "live", n, 10, 60)
        make(ws, "dead", n, 10, 60)
    run(ws, protect_sessions=frozenset({"live"}), protect_last=2)
    assert left(ws, "live") == ["4", "5"]
    assert left(ws, "dead") == []


def test_symlinked_dirs_are_never_followed(ws, tmp_path):
    victim = tmp_path / "outside"
    (victim / "1").mkdir(parents=True)
    (victim / "1" / "content").write_text("keep")
    base = ws / ".dot" / "checkpoints"
    base.mkdir(parents=True)
    (base / "evil").symlink_to(victim)
    out = ws / ".dot" / "tool_outputs"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.symlink_to(victim)
    (victim / "old.log").write_text("keep")
    os.utime(victim / "old.log", (1, 1))
    run(ws)
    assert (victim / "1" / "content").read_text() == "keep"
    assert (victim / "old.log").exists()
