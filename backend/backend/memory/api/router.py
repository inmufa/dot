from dot_contracts.memory import MemoryFact, MemoryIn, MemoryUpdate
from fastapi import Request

from backend.core.api.auth import protected_router
from backend.memory.services.store import MemoryService

router = protected_router(prefix="/v1/memory", tags=["memory"])


def service(request: Request) -> MemoryService:
    return request.app.state.memory


@router.get("")
async def list_memory(
    request: Request, q: str | None = None, limit: int = 100
) -> list[MemoryFact]:
    limit = min(max(limit, 1), 500)
    if q:
        return await service(request).search(q, limit)
    return await service(request).list_facts(limit)


@router.post("", status_code=201)
async def create_memory(request: Request, body: MemoryIn) -> MemoryFact:
    return await service(request).add(body)


@router.put("/{fact_id}")
async def update_memory(
    request: Request, fact_id: str, body: MemoryUpdate
) -> MemoryFact:
    return await service(request).update(fact_id, body)


@router.delete("/{fact_id}")
async def delete_memory(request: Request, fact_id: str) -> dict[str, bool]:
    await service(request).delete(fact_id)
    return {"ok": True}
