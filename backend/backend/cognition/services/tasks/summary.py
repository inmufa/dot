"""Open-task summary for the per-turn reminder and for compaction."""

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.tasks.task_service import TaskService
from backend.core.text import strip_control_tags

_state: dict[str, TaskService] = {}


def bind(maker: async_sessionmaker) -> None:
    """Called once at app start so `open_tasks_summary(session_id)` needs no handle."""
    _state["service"] = TaskService(maker)


async def open_tasks_summary(session_id: str) -> str:
    """One line per unfinished task, or "" when there is none."""
    service = _state.get("service")
    if service is None:
        return ""
    tasks = await service.list_tasks(session_id)
    open_ids = {t.id for t in tasks if t.status != "completed"}
    lines = []
    for t in (t for t in tasks if t.id in open_ids):
        waiting = [b for b in t.blocked_by if b in open_ids]
        waits = f" (blocked by {', '.join(waiting)})" if waiting else ""
        subject = strip_control_tags(" ".join(t.subject.split()))
        lines.append(f"- {t.id} [{t.status}] {subject}{waits}")
    return "\n".join(lines)
