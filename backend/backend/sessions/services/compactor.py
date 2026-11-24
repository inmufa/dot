"""Context compaction: think drop, Read microcompact, then an LLM summary.

History stays append-only. Stages a and b store a model-visible replacement on
the row (`view_content`); stage c folds old rows into a `summary` row
(`compacted_into`). The static prompt prefix is never touched.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.core.exceptions import DomainException
from backend.governance.services.pipeline import Governance
from backend.governance.settings.schema import HookEvent
from backend.routing.clients.llm_types import LLMClient
from backend.sessions.models import Message
from backend.sessions.services.compaction import cut, stages, summarizer
from backend.sessions.services.compaction.restore import Restorer
from backend.sessions.services.compaction.tokens import ContextMeter, rows_tokens
from backend.sessions.services.transcript import TranscriptStore
from backend.sessions.services.transcript_tokens import estimate_tokens

logger = logging.getLogger(__name__)
MAX_AUTO_PER_TURN = 3  # a stuck context must not summarise on every model call
KEEP_RATIO = 0.25  # recent rows kept verbatim, as a share of the context limit


@dataclass
class Outcome:
    compacted: bool
    reason: str | None = None
    tokens_before: int = 0
    tokens_after: int = 0
    stages: list[str] = field(default_factory=list)


def _skipped(reason: str, tokens: int) -> Outcome:
    return Outcome(
        compacted=False, reason=reason, tokens_before=tokens, tokens_after=tokens
    )


@dataclass
class _Plan:
    session_pk: int
    public_id: str
    trigger: str
    system_tokens: int
    before: int
    budget: int
    force: bool
    keep: float = KEEP_RATIO  # share of the limit kept verbatim
    initial: int = 0  # estimated size of the rows before any stage ran

    def left(self, rows: list[Message]) -> int:
        """Context size now: the measured size minus what the stages saved."""
        return self.before - (self.initial - rows_tokens(rows))


class Compactor:
    def __init__(  # noqa: PLR0913
        self,
        *,
        store: TranscriptStore,
        llm: LLMClient,
        restorer: Restorer,
        workspace: str,
        limit: int,
        threshold: float = 0.75,
        gov: Governance | None = None,
        on_compacted: Callable[[str], None] | None = None,
    ) -> None:
        self._store = store
        self._llm = llm
        self._restorer = restorer
        self._workspace = workspace
        self._limit = limit
        self._ratio = threshold
        self._gov = gov
        self._on_compacted = on_compacted
        self.meter = ContextMeter()
        self._blocked: dict[int, int] = {}  # session -> user seq a hook blocked on
        self._autos: dict[int, tuple[int, int]] = {}  # session -> (user seq, runs)

    @property
    def threshold(self) -> int:
        return int(self._limit * self._ratio)

    async def used(self, session_pk: int, system_text: str) -> tuple[int, str]:
        rows = await self._store.load(session_pk)
        return self.meter.estimate(session_pk, estimate_tokens(system_text), rows)

    async def maybe_compact(
        self, session_pk: int, public_id: str, system_text: str
    ) -> Outcome | None:
        """Before a model call: compact when the context passed the threshold."""
        used, _ = await self.used(session_pk, system_text)
        if used < self.threshold:
            return None
        rows = await self._store.load(session_pk)
        # Folded user rows still count: the turn id must survive a summary.
        everyone = await self._store.load(session_pk, include_compacted=True)
        user_seq = max((r.seq for r in everyone if r.role == "user"), default=0)
        if self._blocked.get(session_pk) == user_seq:
            return None  # a PreCompact hook already said no this turn
        seen_seq, runs = self._autos.get(session_pk, (user_seq, 0))
        if seen_seq == user_seq and runs >= MAX_AUTO_PER_TURN:
            return None
        plan = _Plan(
            session_pk,
            public_id,
            "auto",
            estimate_tokens(system_text),
            used,
            self.threshold,
            force=False,
        )
        out = await self._run(plan, rows)
        if out.reason == "blocked":
            self._blocked[session_pk] = user_seq
        if out.compacted:
            self._autos[session_pk] = (
                user_seq,
                (runs if seen_seq == user_seq else 0) + 1,
            )
        return out if out.compacted else None

    async def compact_now(
        self, session_pk: int, public_id: str, system_text: str
    ) -> Outcome:
        """Manual compaction (POST /compact): every stage, regardless of size."""
        rows = await self._store.load(session_pk)
        used, _ = self.meter.estimate(session_pk, estimate_tokens(system_text), rows)
        plan = _Plan(
            session_pk,
            public_id,
            "manual",
            estimate_tokens(system_text),
            used,
            0,
            force=True,
            keep=0.0,  # /compact folds everything but the newest message
        )
        return await self._run(plan, rows)

    async def _run(self, plan: _Plan, rows: list[Message]) -> Outcome:
        if self._gov is not None:
            hook = await self._gov.fire(
                HookEvent.PRE_COMPACT,
                plan.public_id,
                {"trigger": plan.trigger, "tokens": plan.before},
            )
            if hook.blocked:
                logger.info("compaction skipped: PreCompact hook blocked it")
                return _skipped("blocked", plan.before)
        plan.initial = rows_tokens(rows)
        done, rows = await self._cheap_stages(plan, rows)
        summary_seq = None
        if plan.force or plan.left(rows) > plan.budget:
            summary_seq = await self._summarise(plan, rows)
            if summary_seq is not None:
                done.append("summary")
        if not done:
            return _skipped("nothing to compact", plan.before)
        return await self._finish(plan, done, summary_seq)

    async def _cheap_stages(
        self, plan: _Plan, rows: list[Message]
    ) -> tuple[list[str], list[Message]]:
        """Stages a and b; stops early once the context fits (auto trigger)."""
        done: list[str] = []
        for name, fn in (
            ("think", stages.drop_old_think),
            ("microcompact", lambda r: stages.microcompact(r, self._workspace)),
        ):
            if not plan.force and plan.left(rows) <= plan.budget:
                break
            views = fn(rows)
            if not views:
                continue
            await self._store.overlay.set_views(plan.session_pk, views)
            done.append(name)
            rows = await self._store.load(plan.session_pk)
        return done, rows

    async def _summarise(self, plan: _Plan, rows: list[Message]) -> int | None:
        index = cut.choose_cut(rows, int(self._limit * plan.keep))
        if index is None:
            return None
        head = rows[:index]
        try:
            summary = await summarizer.summarize(self._llm, head)
        except DomainException:
            logger.warning("compaction summary failed: model unavailable")
            if plan.trigger == "manual":
                raise
            return None
        everything = await self._store.load(plan.session_pk, include_compacted=True)
        extra, restored = await self._restorer.build(plan.public_id, everything)
        content = summary.render() + (f"\n{extra}" if extra else "")
        return await self._store.overlay.commit_summary(
            plan.session_pk,
            [r.seq for r in head],
            content,
            tainted=summary.tainted or bool(restored),  # file text is repo data
        )

    async def _finish(
        self, plan: _Plan, done: list[str], summary_seq: int | None
    ) -> Outcome:
        after_rows = await self._store.load(plan.session_pk)
        before, after = plan.before, max(1, plan.left(after_rows))
        await self._store.overlay.record(
            plan.session_pk, plan.trigger, done, before, after, summary_seq
        )
        self.meter.reset(plan.session_pk)
        if self._on_compacted:
            self._on_compacted(plan.public_id)
        return Outcome(
            compacted=True, tokens_before=before, tokens_after=after, stages=done
        )
