"""Branch a session: copy the transcript up to a turn boundary into a new one."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.sessions.models import Message, Session
from backend.sessions.services.search import fts

BRANCH_INVALID = 2031
NOTHING_TO_REGENERATE = 2032
_COPIED = (
    "role",
    "content",
    "tool_calls",
    "tool_call_id",
    "reminder",
    "token_count",
    "view_content",
    "tainted",
    "reasoning",
    "meta",
    "created_at",
)
# Rows the engine adds itself; they are not something the user typed.
_SYNTHETIC = ("<system-reminder>", "[Stop hook]")


def _at_boundary(row: Message) -> bool:
    return row.role == "assistant" and not row.tool_calls


def cut_rows(rows: list[Message], from_seq: int) -> list[Message]:
    """Rows with seq < from_seq, trimmed back so a whole turn ends the list."""
    kept = [r for r in rows if r.seq < from_seq and r.role != "summary"]
    while kept and not _at_boundary(kept[-1]):
        kept.pop()  # a dangling user/tool row or an assistant with open calls
    return kept


async def branch(maker: async_sessionmaker, src: Session, from_seq: int) -> Session:
    async with maker() as db:
        rows = list(
            (
                await db.scalars(
                    select(Message)
                    .where(Message.session_id == src.id, Message.rewound.is_(False))
                    .order_by(Message.seq)
                )
            ).all()
        )
        last = max((r.seq for r in rows), default=0)
        if from_seq > last + 1:
            raise DomainException(BRANCH_INVALID)
        kept = cut_rows(rows, from_seq)
        cut = kept[-1].seq if kept else 0
        # Summaries up to the cut stay (rows they folded keep pointing at them);
        # one past the cut would leak later content, so it is left out.
        copy = [r for r in rows if r.seq <= cut]
        live = {r.seq for r in copy if r.role == "summary"}
        new = Session(
            public_id=new_public_id("S"),
            mode=src.mode,
            title=src.title,
            project=src.project,
            effort=src.effort,
            parent_id=src.public_id,
            parent_seq=cut,
        )
        db.add(new)
        await db.flush()
        for r in copy:
            row = Message(session_id=new.id, seq=r.seq, rewound=False)
            for name in _COPIED:
                setattr(row, name, getattr(r, name))
            folded = r.compacted_into
            row.compacted_into = folded if folded in live else None
            db.add(row)
            await fts.index_message(db, new.id, r.seq, r.role, r.content)
        await fts.set_title(db, new.id, new.title)
        await db.commit()
        return new


async def last_user_turn(maker: async_sessionmaker, session_pk: int) -> Message:
    """The last user message the person typed (not an engine-added row).

    A turn that failed before any reply still counts, so Retry can rerun it."""
    async with maker() as db:
        rows = list(
            (
                await db.scalars(
                    select(Message)
                    .where(
                        Message.session_id == session_pk,
                        Message.rewound.is_(False),
                        Message.role.in_(("user", "assistant")),
                    )
                    .order_by(Message.seq.desc())
                )
            ).all()
        )
    for r in rows:
        if r.role == "user" and not r.content.startswith(_SYNTHETIC):
            return r
    raise DomainException(NOTHING_TO_REGENERATE)


async def rewind_from(maker: async_sessionmaker, session_pk: int, seq: int) -> None:
    """Hide every row from `seq` on (files untouched)."""
    async with maker() as db:
        await db.execute(
            update(Message)
            .where(Message.session_id == session_pk, Message.seq >= seq)
            .where(Message.rewound.is_(False))
            .values(rewound=True)
        )
        await db.commit()
