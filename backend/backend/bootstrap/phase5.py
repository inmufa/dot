"""Wires the MCP client and the scheduler (kept apart from the core runtime)."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.engine.react_engine import ReactEngine
from backend.cognition.services.engine.turn import TurnRegistry
from backend.cognition.services.skill_loader import SkillRegistry
from backend.cognition.services.tools.registry import ToolRegistry
from backend.governance.services.pipeline import Governance
from backend.mcp.services.manager import McpManager
from backend.memory.services.store import MemoryService
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient
from backend.scheduler.services.clock import Clock, SystemClock
from backend.scheduler.services.cron_tools import make_cron_tools
from backend.scheduler.services.jobs import JobService
from backend.scheduler.services.maintenance import build_handlers
from backend.scheduler.services.runner import HeadlessRunner
from backend.scheduler.services.scheduler import Scheduler
from backend.sessions.services.session_service import SessionService
from backend.settings import Settings

logger = logging.getLogger(__name__)
Closer = Callable[[], Awaitable[None]]


@dataclass
class Phase5Deps:
    app: FastAPI
    settings: Settings
    maker: async_sessionmaker
    registry: ToolRegistry
    sandbox: SandboxClient
    gov: Governance
    skills: SkillRegistry
    llm: LLMClient
    turns: TurnRegistry
    memory: MemoryService
    react: ReactEngine
    clock: Clock | None = None


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


async def build_phase5(d: Phase5Deps) -> list[Closer]:
    """Start MCP and the scheduler; returns closers to run (in order) at shutdown."""
    s = d.settings
    mcp = McpManager(
        settings=s,
        provider=d.gov.settings,
        registry=d.registry,
        sandbox=d.sandbox,
        maker=d.maker,
        audit=d.gov.audit,
        skills=d.skills,
    )
    jobs = JobService(
        d.maker,
        d.clock or SystemClock(),
        _zone(s.timezone),
        max_jobs=s.schedule_max_jobs,
        jitter_s=s.schedule_jitter_s,
    )
    for tool in make_cron_tools(jobs):
        d.registry.add(tool)
    runner = HeadlessRunner(
        d.react,
        SessionService(d.maker),
        d.turns,
        mode=s.schedule_mode,
        timeout_s=s.schedule_run_timeout_s,
    )
    scheduler = Scheduler(
        jobs,
        jobs.clock,
        runner,
        build_handlers(s, d.memory, d.llm, d.sandbox, jobs, d.maker),
        poll_s=s.schedule_poll_s,
        missed_grace_s=s.schedule_missed_grace_s,
        run_timeout_s=s.schedule_run_timeout_s,
    )
    d.app.state.mcp = mcp
    d.app.state.jobs = jobs
    d.app.state.scheduler = scheduler
    closers: list[Closer] = []
    # Optional parts: a failure here is logged, never a failed boot.
    if s.scheduler_enabled:
        try:
            await scheduler.start()
            closers.append(scheduler.stop)
        except Exception:
            logger.exception("scheduler failed to start; continuing without it")
    try:
        await mcp.start()
    except Exception:
        logger.exception("mcp failed to start; continuing without it")
    closers.append(mcp.stop)
    return closers
