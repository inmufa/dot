from helpers import new_session, parse_sse
from httpx import AsyncClient


async def chat(c: AsyncClient, sid: str, message: str = "go") -> list[dict]:
    resp = await c.post(f"/v1/sessions/{sid}/chat", json={"message": message})
    return parse_sse(resp.text)


async def make(c: AsyncClient, mode: str = "bypass") -> str:
    return await new_session(c, mode)


async def rows(c: AsyncClient, sid: str) -> list[dict]:
    return (await c.get(f"/v1/sessions/{sid}/messages")).json()
