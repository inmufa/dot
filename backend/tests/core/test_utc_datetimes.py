from datetime import UTC, datetime, timedelta, timezone

from dot_contracts.sessions import SessionInfo
from httpx import AsyncClient


def test_naive_datetime_is_serialised_as_utc():
    naive = datetime(2026, 1, 2, 3, 4, 5)  # noqa: DTZ001 - what SQLite hands back
    info = SessionInfo(id="S1", mode="default", created_at=naive)
    assert info.model_dump(mode="json")["created_at"] == "2026-01-02T03:04:05Z"


def test_offset_datetime_is_converted_to_utc():
    local = datetime(2026, 1, 2, 8, 4, 5, tzinfo=timezone(timedelta(hours=5)))
    info = SessionInfo(id="S1", mode="default", created_at=local)
    assert info.created_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


async def test_api_timestamps_carry_a_utc_marker(authed: AsyncClient):
    created = await authed.post("/v1/sessions", json={})
    assert created.status_code == 201
    stamp = created.json()["created_at"]
    assert stamp.endswith(("Z", "+00:00")), stamp
    listed = (await authed.get("/v1/sessions")).json()
    items = listed if isinstance(listed, list) else listed["items"]
    assert items[0]["created_at"].endswith(("Z", "+00:00"))
