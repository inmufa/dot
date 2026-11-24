"""Built-in jobs: memory consolidation, sandbox retention, log hygiene."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.governance.models import Checkpoint
from backend.memory.services.consolidate import consolidate
from backend.memory.services.store import MemoryService
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient
from backend.scheduler.services.jobs import JobService
from backend.sessions.models import Session
from backend.settings import Settings

logger = logging.getLogger(__name__)
Handler = Callable[[], Awaitable[str]]
RUN_HISTORY_DAYS = 30
LIVE_HOURS = 24  # sessions active this recently keep their newest checkpoints
PROTECT_LAST = 50


@dataclass(frozen=True)
class Builtin:
    key: str
    cron: str


BUILTINS = (
    Builtin("builtin:memory", "30 3 * * *"),
    Builtin("builtin:retention", "15 4 * * *"),
    Builtin("builtin:logs", "45 4 * * 0"),
)


def build_handlers(
    settings: Settings,
    memory: MemoryService,
    llm: LLMClient,
    sandbox: SandboxClient,
    jobs: JobService,
    maker: async_sessionmaker,
) -> dict[str, Handler]:
    async def memory_job() -> str:
        rep = await consolidate(memory, llm)
        return f"exact {rep.exact_removed}, merged {rep.merged_groups}"

    async def live_sessions() -> list[str]:
        since = datetime.now(UTC) - timedelta(hours=LIVE_HOURS)
        async with maker() as db:
            rows = await db.scalars(
                select(Session.public_id)
                .join(Checkpoint, Checkpoint.session_id == Session.id)
                .where(Checkpoint.created_at >= since)
                .distinct()
            )
            return list(rows)

    async def retention_job() -> str:
        r = await sandbox.post(
            "scheduler",
            "/internal/retention",
            {
                "checkpoint_days": settings.retention_checkpoint_days,
                "checkpoint_max_bytes": settings.retention_checkpoint_max_bytes,
                "outputs_days": settings.retention_outputs_days,
                "protect_sessions": await live_sessions(),
                "protect_last": PROTECT_LAST,
            },
        )
        if not r.ok:
            raise DomainException(4001)
        d = r.data
        return (
            f"checkpoints {d['checkpoints_removed']}, outputs {d['outputs_removed']}, "
            f"{d['bytes_freed']} bytes"
        )

    async def logs_job() -> str:
        return f"run history rows removed: {await jobs.prune_history(RUN_HISTORY_DAYS)}"

    return {
        "builtin:memory": memory_job,
        "builtin:retention": retention_job,
        "builtin:logs": logs_job,
    }
