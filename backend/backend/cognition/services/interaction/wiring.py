"""Builds the agent-tool services (tasks, questions, plan mode, subagents)."""

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.interaction.agent_services import AgentServices
from backend.cognition.services.subagents.runner import SubagentRunner
from backend.cognition.services.tasks import summary
from backend.cognition.services.tasks.task_service import TaskService
from backend.cognition.services.tools.registry import ToolRegistry
from backend.governance.services.approvals import ApprovalRegistry
from backend.governance.services.pipeline import Governance
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.services.transcript import TranscriptStore
from backend.settings import Settings


def build_agent_services(  # noqa: PLR0913
    *,
    settings: Settings,
    maker: async_sessionmaker,
    store: TranscriptStore,
    gov: Governance,
    approvals: ApprovalRegistry,
    registry: ToolRegistry,
    llm: LLMClient,
    sandbox: SandboxClient,
) -> AgentServices:
    summary.bind(maker)
    agent = AgentServices(
        maker=maker,
        store=store,
        gov=gov,
        approvals=approvals,
        registry=registry,
        tasks=TaskService(maker),
        question_timeout_s=settings.question_timeout_s,
        approval_timeout_s=settings.approval_timeout_s,
    )
    agent.subagents = SubagentRunner(
        llm=llm,
        registry=registry,
        agent=agent,
        sandbox=sandbox,
        workspace=str(settings.workspace.absolute()),
        context_limit=lambda: settings.llm_context_limit,
        slots=settings.llm_parallel_slots,
    )
    return agent
