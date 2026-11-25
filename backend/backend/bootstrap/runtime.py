"""Lifespan wiring: builds every service once and binds it to `app.state`."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from backend.bootstrap.features import build_features
from backend.bootstrap.phase5 import Phase5Deps, build_phase5
from backend.cognition.services.context.wiring import ContextServices, build_context
from backend.cognition.services.engine.prompt_compiler import PromptCompiler
from backend.cognition.services.engine.react_engine import ReactEngine
from backend.cognition.services.engine.tool_runner import ToolRunner
from backend.cognition.services.engine.turn import TurnRegistry
from backend.cognition.services.interaction.agent_services import AgentServices
from backend.cognition.services.interaction.wiring import build_agent_services
from backend.cognition.services.skill_loader import SkillRegistry, sandbox_probe
from backend.cognition.services.tools.executor import default_registry
from backend.cognition.services.tools.registry import ToolRegistry
from backend.cognition.services.tools.web import add_web_tools
from backend.core.db import create_schema, make_engine, make_sessionmaker
from backend.governance.services.approvals import ApprovalRegistry
from backend.governance.services.pipeline import Governance
from backend.governance.wiring import build_governance
from backend.routing.clients.llama_client import LlamaClient, Sampling
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient
from backend.routing.services.budget import LimitWatcher
from backend.sessions.services.transcript import TranscriptStore
from backend.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    engine: AsyncEngine
    llm: LLMClient
    sandbox: SandboxClient
    owns_llm: bool
    owns_sandbox: bool
    closers: list[Callable[[], Awaitable[None]]] = field(default_factory=list)

    async def close(self) -> None:
        for closer in reversed(self.closers):  # MCP and scheduler first
            try:
                await closer()
            except Exception:
                logger.exception("shutdown step failed")
        if self.owns_llm:
            await self.llm.aclose()
        if self.owns_sandbox:
            await self.sandbox.aclose()
        await self.engine.dispose()


async def _skills(
    settings: Settings, sandbox: SandboxClient
) -> tuple[SkillRegistry, ToolRegistry, list[Callable[[], Awaitable[None]]]]:
    skills = SkillRegistry(
        settings.skills_dir,
        settings.user_skills_dir.expanduser(),
        settings.workspace.absolute(),
    )
    skills.probe = sandbox_probe(sandbox)
    registry = default_registry(skills)
    web_closers = add_web_tools(registry, settings)
    skills.set_environment({d.name for d in registry.definitions()})
    await skills.ensure_binaries()
    return skills, registry, web_closers


def _tool_runner(
    settings: Settings,
    parts: "_Parts",
    agent: AgentServices,
    ctx: ContextServices,
) -> ToolRunner:
    return ToolRunner(
        registry=parts.registry,
        gov=parts.gov,
        approvals=parts.approvals,
        store=parts.store,
        sandbox=parts.sandbox,
        workspace=str(settings.workspace.absolute()),
        approval_timeout_s=settings.approval_timeout_s,
        agent=agent,
        on_result=ctx.tiers.on_tool,
    )


@dataclass
class _Parts:
    maker: async_sessionmaker
    registry: ToolRegistry
    store: TranscriptStore
    approvals: ApprovalRegistry
    gov: Governance
    sandbox: SandboxClient
    llm: LLMClient
    turns: TurnRegistry


def _react(
    settings: Settings,
    parts: _Parts,
    skills: SkillRegistry,
    agent: AgentServices,
    ctx: ContextServices,
) -> ReactEngine:
    runner = _tool_runner(settings, parts, agent, ctx)
    return ReactEngine(
        llm=parts.llm,
        registry=parts.registry,
        runner=runner,
        store=parts.store,
        compiler=PromptCompiler(parts.registry.core_definitions()),
        cwd=str(settings.workspace.absolute()),
        context_limit=lambda: settings.llm_context_limit,
        max_iterations=settings.max_iterations,
        skills=skills,
        gov=parts.gov,
        agent=agent,
        compactor=ctx.compactor,
        tiers=ctx.tiers,
    )


def _bind(app: FastAPI, **items: object) -> None:
    for key, value in items.items():
        setattr(app.state, key, value)


async def build_runtime(
    app: FastAPI,
    settings: Settings,
    llm: LLMClient | None,
    sandbox: SandboxClient | None,
) -> Runtime:
    engine = make_engine(settings)
    watcher = LimitWatcher(settings) if llm is None else None
    if watcher:
        await watcher.refresh()  # seed limit and slots; the llm may still be loading
        watcher.start()
    await create_schema(engine)
    maker = make_sessionmaker(engine)
    llm_client = llm or LlamaClient(
        settings.llm_base_url,
        settings.llm_model,
        sampling=Sampling(
            thinking=settings.llm_thinking,
            temperature=settings.llm_temperature,
            top_p=settings.llm_top_p,
            top_k=settings.llm_top_k,
            presence_penalty=settings.llm_presence_penalty,
            max_tokens=settings.llm_max_tokens,
        ),
        debug_file=settings.llm_debug_file,
    )
    sandbox_client = sandbox or SandboxClient(
        settings.sandbox_url, settings.sandbox_token
    )
    skills, registry, web_closers = await _skills(settings, sandbox_client)
    store = TranscriptStore(maker)
    approvals = ApprovalRegistry()
    turns = TurnRegistry()
    gov = build_governance(settings, maker, store, sandbox_client, turns)
    ctx = await build_context(
        settings=settings,
        maker=maker,
        registry=registry,
        store=store,
        llm=llm_client,
        sandbox=sandbox_client,
        gov=gov,
    )
    agent = build_agent_services(
        settings=settings,
        maker=maker,
        store=store,
        gov=gov,
        approvals=approvals,
        registry=registry,
        llm=llm_client,
        sandbox=sandbox_client,
    )
    parts = _Parts(
        maker, registry, store, approvals, gov, sandbox_client, llm_client, turns
    )
    ctx.bind(app.state)
    react = _react(settings, parts, skills, agent, ctx)
    _bind(
        app,
        agent=agent,
        settings=settings,
        skills=skills,
        engine=engine,
        sessions=maker,
        llm=llm_client,
        sandbox=sandbox_client,
        approvals=approvals,
        turns=turns,
        gov=gov,
        audit=gov.audit,
        checkpoints=gov.checkpoints,
        react=react,
    )
    deps = Phase5Deps(
        app,
        settings,
        maker,
        registry,
        sandbox_client,
        gov,
        skills,
        llm_client,
        turns,
        ctx.memory,
        react,
    )
    closers = [*await build_phase5(deps), *await build_features(deps)]
    return Runtime(
        engine,
        llm_client,
        sandbox_client,
        llm is None,
        sandbox is None,
        [
            *web_closers,
            *closers,
            *([watcher.aclose] if watcher else []),
        ],  # closed last-in first: MCP and scheduler lead
    )
