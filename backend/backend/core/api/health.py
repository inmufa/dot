import logging

from fastapi import APIRouter, Request
from sqlalchemy import text

from backend.core.exceptions import DomainException

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)
NOT_READY = 1008


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness: touches nothing."""
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
async def ready(request: Request) -> dict[str, str]:
    """Readiness: database, sandbox /health and llama /health all answer."""
    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("not ready: database check failed: %s", type(exc).__name__)
        raise DomainException(NOT_READY) from exc
    state = request.app.state
    for name, probe in (("sandbox", state.sandbox.health), ("llm", state.llm.health)):
        if not await probe():
            logger.warning("not ready: %s health check failed", name)
            raise DomainException(NOT_READY)
    return {"status": "ready"}
