"""Bridges the engine to an SSE byte stream with stop and disconnect handling."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from dot_contracts.events import DoneEvent, ErrorEvent, StreamEvent
from pydantic import BaseModel

from backend.cognition.services.engine.react_engine import ReactEngine
from backend.cognition.services.engine.turn import Turn, TurnRegistry

logger = logging.getLogger(__name__)
INTERNAL_ERROR = 1000


def sse(event: BaseModel) -> str:
    return f"data: {event.model_dump_json()}\n\n"


_background: set[asyncio.Task[None]] = set()


async def _pump(
    engine: ReactEngine,
    turn: Turn,
    text: str,
    queue: asyncio.Queue[StreamEvent | None],
    after: Callable[[], Awaitable[None]] | None = None,
) -> None:
    try:
        async for event in engine.run(turn, text):
            await queue.put(event)
        if after is not None:  # fire and forget: never delays the stream
            job = asyncio.create_task(after())
            _background.add(job)
            job.add_done_callback(_background.discard)
    except asyncio.CancelledError:
        await queue.put(await engine.abort(turn))
    except Exception:
        logger.exception("turn crashed")
        await queue.put(ErrorEvent(code=INTERNAL_ERROR, message="Internal error"))
        await queue.put(DoneEvent(stop_reason="error"))
    finally:
        await queue.put(None)


def stream_turn(
    engine: ReactEngine,
    registry: TurnRegistry,
    turn: Turn,
    text: str,
    after: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    """Start the turn task now and return its SSE stream.

    The caller must have claimed the session. The task is registered and its
    release is tied to the task itself, so the claim is freed on every exit
    path, even when the response body is never iterated (early disconnect).
    """
    queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
    task = asyncio.create_task(_pump(engine, turn, text, queue, after))
    registry.attach(turn.public_id, task)

    def _finished(done: asyncio.Task[None]) -> None:
        registry.release(turn.public_id, done)
        queue.put_nowait(None)  # wake the reader if the task died before running

    task.add_done_callback(_finished)
    return _drain(queue, task)


async def _drain(
    queue: asyncio.Queue[StreamEvent | None], task: asyncio.Task[None]
) -> AsyncIterator[str]:
    try:
        while (event := await queue.get()) is not None:
            yield sse(event)
    finally:
        task.cancel()  # client went away or the stream ended: stop the turn
        with contextlib.suppress(asyncio.CancelledError):
            await task
