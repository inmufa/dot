import json

import pytest
from helpers import new_session
from httpx import AsyncClient
from mcp_helpers import (
    http_server,
    run_turn,
    search_and_call,
    tool_events,
    wait_status,
)


def user_config(settings, servers: dict) -> None:
    path = settings.user_settings_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mcpServers": servers}))


@pytest.mark.parametrize("kind", ["http", "sse"])
async def test_remote_server_end_to_end(authed: AsyncClient, settings, llm, kind):
    with http_server(kind) as port:
        path = "mcp" if kind == "http" else "sse"
        user_config(
            settings,
            {
                "remote": {
                    "type": kind,
                    "url": f"http://127.0.0.1:{port}/{path}",
                    "allowHosts": ["127.0.0.1"],
                }
            },
        )
        row = await wait_status(authed, "remote", "connected")
        assert row["transport"] == kind
        assert row["scope"] == "user"
        assert row["trusted"] is True
        llm.scripts = search_and_call("mcp__remote__echo", {"text": "net"})
        sid = await new_session(authed, "bypass")
        out = tool_events(await run_turn(authed, sid))
        assert out[1]["output"] == "echo: net"
        msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
        assert [m["tainted"] for m in msgs if m["role"] == "tool"] == [False, True]


async def test_loopback_url_is_blocked_without_allow_host(authed, settings):
    with http_server() as port:
        user_config(
            settings, {"r": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}}
        )
        row = await wait_status(authed, "r", "failed")
        assert row["tool_count"] == 0


async def test_header_reference_outside_the_allowlist_fails_closed(
    authed, settings, monkeypatch
):
    monkeypatch.setenv("AWS_SECRET", "s3")
    user_config(
        settings,
        {
            "r": {
                "url": "https://mcp.example.com/mcp",
                "headers": {"Authorization": "Bearer ${AWS_SECRET}"},
            }
        },
    )
    row = await wait_status(authed, "r", "failed")
    assert row["tool_count"] == 0
