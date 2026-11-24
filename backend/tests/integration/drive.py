"""Sync driver for the public API: SSE reading, inline approval answers."""

import json
from collections.abc import Iterator

import httpx

TOKEN = "i" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def new_session(base: str, mode: str | None = None) -> str:
    body = {"mode": mode} if mode else None
    r = httpx.post(f"{base}/v1/sessions", json=body, headers=AUTH)
    assert r.status_code == httpx.codes.CREATED, r.text
    return r.json()["id"]


def events(base: str, sid: str, message: str) -> Iterator[dict]:
    url = f"{base}/v1/sessions/{sid}/chat"
    with httpx.stream(
        "POST", url, json={"message": message}, headers=AUTH, timeout=40.0
    ) as resp:
        assert resp.status_code == httpx.codes.OK, resp.read()
        for line in resp.iter_lines():
            if line.startswith("data: "):
                yield json.loads(line[6:])


def run_turn(base: str, sid: str, message: str, decision: str = "allow") -> list[dict]:
    """Collect a turn; every approval_required is answered with `decision`."""
    out = []
    for ev in events(base, sid, message):
        out.append(ev)
        if ev["type"] == "approval_required":
            r = httpx.post(
                f"{base}/v1/approvals/{ev['approval_id']}/resolve",
                json={"decision": decision},
                headers=AUTH,
            )
            assert r.json() == {"ok": True}
    return out


def audit(base: str, sid: str) -> list[dict]:
    r = httpx.get(f"{base}/v1/audit?session={sid}&limit=200", headers=AUTH)
    return r.json()["items"]
