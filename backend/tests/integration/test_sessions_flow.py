"""Session management over real HTTP: search, regenerate, branch, export, delete."""

import json

import httpx
import pytest
from drive import AUTH, new_session, run_turn
from fake_llama import FakeLlama, Turn

pytestmark = pytest.mark.integration


def _get(base: str, path: str) -> httpx.Response:
    return httpx.get(f"{base}{path}", headers=AUTH)


def _post(base: str, path: str, body: dict | None = None) -> httpx.Response:
    return httpx.post(f"{base}{path}", json=body, headers=AUTH, timeout=40.0)


def test_search_regenerate_branch_export_delete(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(content="Narwhals live in the Arctic."), Turn(content="Retry.")])
    sid = new_session(backend_url, "default")
    run_turn(backend_url, sid, "where do narwhals live")

    hits = _get(backend_url, "/v1/sessions?q=arctic").json()
    assert [h["id"] for h in hits] == [sid]
    assert hits[0]["message_count"] == 2

    resp = _post(backend_url, f"/v1/sessions/{sid}/regenerate")
    frames = [json.loads(x[6:]) for x in resp.text.split("\n\n") if x]
    assert frames[-1] == {"type": "done", "stop_reason": "end_turn"}
    texts = [
        m["content"] for m in _get(backend_url, f"/v1/sessions/{sid}/messages").json()
    ]
    assert texts == ["where do narwhals live", "Retry."]
    assert _get(backend_url, "/v1/sessions?q=arctic").json() == []  # old answer hidden

    last = _get(backend_url, f"/v1/sessions/{sid}/messages").json()[-1]["seq"]
    branch = _post(backend_url, f"/v1/sessions/{sid}/branch", {"from_seq": last + 1})
    new = branch.json()["session"]
    assert new["parent_id"] == sid
    assert new["message_count"] == 2

    md = _get(backend_url, f"/v1/sessions/{new['id']}/export")
    assert "where do narwhals live" in md.text
    assert md.headers["content-type"].startswith("text/markdown")

    btw = _post(backend_url, f"/v1/sessions/{sid}/btw", {"question": "tl;dr?"})
    assert btw.status_code == 200
    assert (
        _get(backend_url, f"/v1/sessions/{sid}/messages").json()[-1]["content"]
        == "Retry."
    )

    for s in (sid, new["id"]):
        r = httpx.delete(f"{backend_url}/v1/sessions/{s}?confirm={s}", headers=AUTH)
        assert r.json() == {"ok": True}
    ids = {s["id"] for s in _get(backend_url, "/v1/sessions").json()}
    assert sid not in ids
    assert new["id"] not in ids
