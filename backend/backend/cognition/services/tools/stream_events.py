"""Forward stream events a tool emits while it is still running."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from typing import Any

from dot_contracts.events import StreamEvent


@dataclass
class Done:
    """Last item of `drain`: the awaited work's value."""

    value: Any


async def drain(
    queue: asyncio.Queue[StreamEvent], work: Awaitable[Any]
) -> AsyncIterator[StreamEvent | Done]:
    """Run `work`, yielding queued events as they arrive, then `Done(result)`.

    Cancelling the consumer cancels the work (and so any subagents inside it).
    """
    task = asyncio.ensure_future(work)
    try:
        while not task.done() or not queue.empty():
            if not queue.empty():
                yield queue.get_nowait()
                continue
            getter = asyncio.ensure_future(queue.get())
            await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter.done():
                yield getter.result()
            else:
                getter.cancel()
        yield Done(task.result())
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
