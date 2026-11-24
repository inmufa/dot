"""What the ReAct loop needs from the context services (system text, compaction)."""

from dot_contracts.events import CompactionEvent, StreamEvent

from backend.cognition.services.context.tiers import ContextTiers
from backend.cognition.services.engine.prompt_compiler import PromptCompiler
from backend.sessions.services.compactor import Compactor


class EngineContext:
    def __init__(
        self,
        compiler: PromptCompiler,
        compactor: Compactor | None,
        tiers: ContextTiers | None,
    ) -> None:
        self._compiler = compiler
        self.compactor = compactor
        self.tiers = tiers

    def system_for(self, suffix: str) -> str:
        """Static prefix + boundary + the per-session suffix."""
        return self._compiler.with_suffix(suffix)

    async def system(self, session: str) -> str:
        if self.tiers is None:
            return self._compiler.system_prompt
        return self.system_for((await self.tiers.suffix(session)).text)

    def begin_turn(self, session: str) -> None:
        if self.tiers is not None:
            self.tiers.begin_turn(session)

    def take_reminder(self, session: str) -> str:
        """Subdirectory DOT.md text found last turn (as a system-reminder)."""
        return self.tiers.take_reminder(session) if self.tiers else ""

    async def precompact(
        self, session_pk: int, session: str, system: str
    ) -> list[StreamEvent]:
        """Compact before a model call when the context passed the threshold."""
        if self.compactor is None:
            return []
        out = await self.compactor.maybe_compact(session_pk, session, system)
        if out is None:
            return []
        return [
            CompactionEvent(
                tokens_before=out.tokens_before,
                tokens_after=out.tokens_after,
                stages=out.stages,
            )
        ]

    def observe(self, session_pk: int, prompt_tokens: int | None, seq: int) -> None:
        if self.compactor:
            self.compactor.meter.observe(session_pk, prompt_tokens, seq)
