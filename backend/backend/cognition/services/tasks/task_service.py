"""Task DAG stored in SQLite only (the sandbox protects `.dot`, so no file mirror)."""

import asyncio
from dataclasses import dataclass

from dot_contracts.tasks import TaskInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.models import Task
from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.core.session_ids import root_of

TASK_NOT_FOUND = 4004
MAX_TASKS = 200
DESCRIPTION_MAX = 4000
STATUSES = ("pending", "in_progress", "completed")
_DONE = "completed"


class TaskError(Exception):
    """A rule violation, reported to the model as plain text."""


@dataclass
class TaskPatch:
    subject: str | None = None
    description: str | None = None
    status: str | None = None
    blocked_by: list[str] | None = None


def to_info(row: Task) -> TaskInfo:
    return TaskInfo(
        id=row.public_id,
        subject=row.subject,
        description=row.description,
        status=row.status,  # type: ignore[arg-type]
        blocked_by=list(row.blocked_by or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def reaches(graph: dict[str, list[str]], start: str, target: str) -> bool:
    """True when `target` can be reached from `start` following blocked_by edges."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            stack.extend(graph.get(node, []))
    return False


class TaskService:
    def __init__(self, maker: async_sessionmaker) -> None:
        self._maker = maker
        # Tool calls run in parallel: serialise writes so two updates cannot
        # each pass the cycle check and still form a cycle together.
        self._lock = asyncio.Lock()

    async def _rows(self, session: str) -> list[Task]:
        async with self._maker() as db:
            q = select(Task).where(Task.session_id == root_of(session))
            return list((await db.scalars(q.order_by(Task.id))).all())

    async def list_tasks(self, session: str) -> list[TaskInfo]:
        return [to_info(r) for r in await self._rows(session)]

    async def get(self, session: str, public_id: str) -> TaskInfo:
        for row in await self._rows(session):
            if row.public_id == public_id:
                return to_info(row)
        raise DomainException(TASK_NOT_FOUND)

    async def create(
        self,
        session: str,
        subject: str,
        description: str = "",
        blocked_by: list[str] | None = None,
    ) -> TaskInfo:
        async with self._lock:
            return await self._create(session, subject, description, blocked_by)

    async def _create(
        self,
        session: str,
        subject: str,
        description: str,
        blocked_by: list[str] | None,
    ) -> TaskInfo:
        blockers = list(dict.fromkeys(blocked_by or []))
        existing = await self._rows(session)
        if len(existing) >= MAX_TASKS:
            msg = f"too many tasks (max {MAX_TASKS})"
            raise TaskError(msg)
        known = {r.public_id for r in existing}
        if missing := [b for b in blockers if b not in known]:
            msg = f"unknown blocker task(s): {', '.join(missing)}"
            raise TaskError(msg)
        async with self._maker() as db:
            row = Task(
                public_id=new_public_id("T"),
                session_id=root_of(session),
                subject=subject.strip()[:200],
                description=description[:DESCRIPTION_MAX],
                blocked_by=blockers,
            )
            db.add(row)
            await db.commit()
            return to_info(row)

    async def update(self, session: str, public_id: str, patch: TaskPatch) -> TaskInfo:
        async with self._lock:
            return await self._update(session, public_id, patch)

    async def _update(self, session: str, public_id: str, patch: TaskPatch) -> TaskInfo:
        rows = {r.public_id: r for r in await self._rows(session)}
        if public_id not in rows:
            raise DomainException(TASK_NOT_FOUND)
        graph = {k: list(r.blocked_by or []) for k, r in rows.items()}
        if patch.blocked_by is not None:
            graph[public_id] = self._check_blockers(rows, public_id, graph, patch)
        status = patch.status or rows[public_id].status
        if status not in STATUSES:
            msg = f"status must be one of {', '.join(STATUSES)}"
            raise TaskError(msg)
        if status != "pending" and (patch.status or patch.blocked_by is not None):
            open_ = [b for b in graph[public_id] if rows[b].status != _DONE]
            if open_:
                msg = (
                    f"cannot set {public_id} to {status}: blocked by open task(s) "
                    f"{', '.join(open_)}. Finish those first."
                )
                raise TaskError(msg)
        return await self._save(public_id, patch, graph[public_id], status)

    @staticmethod
    def _check_blockers(
        rows: dict[str, Task],
        public_id: str,
        graph: dict[str, list[str]],
        patch: TaskPatch,
    ) -> list[str]:
        blockers = list(dict.fromkeys(patch.blocked_by or []))
        if missing := [b for b in blockers if b not in rows]:
            msg = f"unknown blocker task(s): {', '.join(missing)}"
            raise TaskError(msg)
        for b in blockers:
            if reaches(graph, b, public_id):
                msg = f"dependency cycle: {b} already depends on {public_id}"
                raise TaskError(msg)
        return blockers

    async def _save(
        self, public_id: str, patch: TaskPatch, blockers: list[str], status: str
    ) -> TaskInfo:
        async with self._maker() as db:
            row = await db.scalar(select(Task).where(Task.public_id == public_id))
            if row is None:
                raise DomainException(TASK_NOT_FOUND)
            row.status = status
            row.blocked_by = blockers
            if patch.subject:
                row.subject = patch.subject.strip()[:200]
            if patch.description is not None:
                row.description = patch.description[:DESCRIPTION_MAX]
            await db.commit()
            return to_info(row)
