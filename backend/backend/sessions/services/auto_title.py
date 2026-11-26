"""AI chat titles: once the first exchange is done, replace the first-message placeholder."""

import logging
import re

from sqlalchemy import select

from backend.core.exceptions import DomainException
from backend.routing.clients.llm_types import LLMClient
from backend.sessions.models import Session
from backend.sessions.services.session_service import TITLE_MAX, SessionService

logger = logging.getLogger(__name__)
_SNIPPET = 400
_MAX_ATTEMPTS = 6  # keep retrying across turns until it sticks or the chat is old
_SYSTEM = (
    "Write a short title for this chat: 2 to 5 words, in the language the user writes in. "
    "Reply with the title only, no quotes, no trailing period."
)


def placeholder(first_user_text: str) -> str | None:
    """What title_from stores; a title that still equals it was never renamed."""
    text = " ".join(first_user_text.split())
    # A pasted chat log often starts "[date] Name: ...": drop that noise for the fallback.
    text = re.sub(r"^\[[^\]]+\]\s*[^:]{1,40}:\s*", "", text, count=1)
    return text[:TITLE_MAX] or None


_SMALL = frozenset(
    [
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "vs",
        "via",
        "with",
    ]
)  # stay lower-case inside a title


def title_case(title: str) -> str:
    """Capitalize each word except short joiners; words with inner capitals or digits are kept."""
    if re.search(r"[:/\\_=@#]|\w\.\w", title):
        return title  # URLs, paths, identifiers and code stay as written
    words = title.split(" ")
    out = []
    for i, w in enumerate(words):
        keep = any(c.isupper() for c in w[1:]) or any(c.isdigit() for c in w)
        if keep or not w[:1].isalpha():
            out.append(w)
        elif i not in {0, len(words) - 1} and w.lower() in _SMALL:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def clean(raw: str) -> str | None:
    line = next((x for x in raw.strip().splitlines() if x.strip()), "")
    title = " ".join(line.split()).strip("\"'`*# ").rstrip(".")
    return title_case(title)[:TITLE_MAX] or None


async def retitle(sessions: SessionService, llm: LLMClient, public_id: str) -> None:
    """Name the chat once, after its first exchange, if the title was never renamed."""
    try:
        rows = await sessions.messages(public_id)
        users = [m for m in rows if m.role == "user"]
        if not users:
            return
        row = await sessions.get(public_id)
        # Retry across turns: a busy model or a race with the next message must not
        # strand the chat on its placeholder title forever.
        if row.title != placeholder(users[0].content) or len(users) > _MAX_ATTEMPTS:
            return
        convo = "\n".join(
            f"{m.role}: {' '.join(m.content.split())[:_SNIPPET]}"
            for m in rows
            if m.role in {"user", "assistant"} and m.content.strip()
        )[:2000]
        raw = await llm.complete(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": convo},
            ],
            max_tokens=32,
            thinking=False,
        )
        title = clean(raw)
        if title:
            await sessions.set_title_if(row.id, placeholder(users[0].content), title)
    except DomainException:
        logger.info("auto title skipped: model unavailable")
    except Exception:
        logger.exception("auto title failed")


async def backfill(
    sessions: SessionService, llm: LLMClient, maker, limit: int = 40
) -> None:
    """Name chats still on their first-message placeholder (the title call may have failed earlier)."""
    async with maker() as db:
        ids = list(
            (
                await db.scalars(
                    select(Session.public_id)
                    .where(Session.title.is_not(None))
                    .order_by(Session.id.desc())
                    .limit(limit)
                )
            ).all()
        )
    for pid in ids:
        await retitle(sessions, llm, pid)
