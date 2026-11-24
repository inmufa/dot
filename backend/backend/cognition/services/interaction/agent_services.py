"""Handles the agent tools need beyond the sandbox (DB, questions, subagents)."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.interaction.activations import ActivationStore
from backend.cognition.services.interaction.questions import QuestionRegistry
from backend.cognition.services.tasks.summary import open_tasks_summary
from backend.cognition.services.tasks.task_service import TaskService
from backend.governance.services.approvals import ApprovalRegistry
from backend.governance.services.pipeline import Governance
from backend.sessions.services.session_service import SessionService
from backend.sessions.services.transcript import TranscriptStore

if TYPE_CHECKING:
    from backend.cognition.services.subagents.runner import SubagentRunner
    from backend.cognition.services.tools.registry import ToolRegistry


@dataclass
class AgentServices:
    maker: async_sessionmaker
    store: TranscriptStore
    gov: Governance
    approvals: ApprovalRegistry
    registry: "ToolRegistry"
    tasks: TaskService
    questions: QuestionRegistry = field(default_factory=QuestionRegistry)
    activations: ActivationStore = field(default_factory=ActivationStore)
    question_timeout_s: float = 300.0
    approval_timeout_s: float = 300.0
    subagents: "SubagentRunner | None" = None
    previous_mode: dict[str, str] = field(default_factory=dict)

    @property
    def sessions(self) -> SessionService:
        return SessionService(self.maker)

    async def reminder_extra(self, session_id: str) -> str:
        """Per-turn reminder blocks: deferred tool names and the open task list."""
        parts = []
        if names := self.registry.deferred_names():
            parts.append(f"Deferred tools available via ToolSearch: {', '.join(names)}")
        if tasks := await open_tasks_summary(session_id):
            parts.append(f"Open tasks:\n{tasks}")
        if not parts:
            return ""
        return "\n<system-reminder>\n" + "\n".join(parts) + "\n</system-reminder>"
