import asyncio
import json
from collections.abc import Callable

from fastapi import FastAPI
from httpx import AsyncClient


def parse_sse(text: str) -> list[dict]:
    blocks = [b for b in text.split("\n\n") if b]
    assert all(b.startswith("data: ") for b in blocks)
    return [json.loads(b[len("data: ") :]) for b in blocks]


async def new_session(c: AsyncClient, mode: str | None = None) -> str:
    r = await c.post("/v1/sessions", json={"mode": mode} if mode else None)
    assert r.status_code == 201
    return r.json()["id"]


def start_chat(c: AsyncClient, sid: str, msg: str = "go") -> asyncio.Task:
    return asyncio.create_task(
        c.post(f"/v1/sessions/{sid}/chat", json={"message": msg})
    )


async def until(cond: Callable[[], bool], limit_s: float = 5) -> None:
    async with asyncio.timeout(limit_s):
        while not cond():  # noqa: ASYNC110
            await asyncio.sleep(0.01)


async def resolve_next(app: FastAPI, c: AsyncClient, decision: str) -> str:
    await until(lambda: bool(app.state.approvals.pending_ids()))
    aid = app.state.approvals.pending_ids()[0]
    r = await c.post(f"/v1/approvals/{aid}/resolve", json={"decision": decision})
    assert r.json() == {"ok": True}
    return aid


def types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]
