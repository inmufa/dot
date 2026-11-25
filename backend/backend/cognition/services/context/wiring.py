"""Builds the context services (memory, DOT.md tiers, compactor) for the app."""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.context.tiers import ContextTiers
from backend.cognition.services.tools.registry import ToolRegistry
from backend.governance.services.pipeline import Governance
from backend.memory.services.store import MemoryService
from backend.memory.services.tool import make_memory_tools
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.services.compaction.restore import Restorer
from backend.sessions.services.compactor import Compactor
from backend.sessions.services.transcript import TranscriptStore
from backend.settings import Settings


def _task_source() -> Callable[[str], Awaitable[str]] | None:
    """The open-task summary, when the task store module exists."""
    try:
        mod = importlib.import_module("backend.cognition.services.tasks.summary")
    except ImportError:
        return None
    return getattr(mod, "open_tasks_summary", None)


@dataclass
class ContextServices:
    store: TranscriptStore
    memory: MemoryService
    tiers: ContextTiers
    compactor: Compactor

    def bind(self, state: Any) -> None:
        state.store = self.store
        state.memory = self.memory
        state.tiers = self.tiers
        state.compactor = self.compactor


async def build_context(  # noqa: PLR0913
    *,
    settings: Settings,
    maker: async_sessionmaker,
    registry: ToolRegistry,
    store: TranscriptStore,
    llm: LLMClient,
    sandbox: SandboxClient,
    gov: Governance,
) -> ContextServices:
    workspace = str(settings.workspace.absolute())
    memory = MemoryService(maker, settings.memory_dir)
    await memory.reindex()
    for tool in make_memory_tools(memory):
        registry.add(tool)
    tiers = ContextTiers(
        sandbox=sandbox,
        workspace=workspace,
        global_rules=settings.global_rules_path,
        user_rules=settings.user_rules_path,
        memory=memory,
    )
    compactor = Compactor(
        store=store,
        llm=llm,
        restorer=Restorer(sandbox, workspace, _task_source()),
        workspace=workspace,
        limit=lambda: settings.llm_context_limit,
        threshold=settings.compact_threshold,
        max_tokens=settings.compact_max_tokens,
        gov=gov,
        on_compacted=tiers.invalidate,
    )
    return ContextServices(store, memory, tiers, compactor)
