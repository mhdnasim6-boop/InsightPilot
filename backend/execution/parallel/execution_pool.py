"""ExecutionPool: bounds how many steps run concurrently, via a plain asyncio.Semaphore.

No threads, no process pool, no external queue — everything runs on one
process's event loop, per this phase's own constraint. The default of 10
is generous enough that real plans (rarely more than a handful of steps)
are never throttled in practice; it exists mainly so a future large plan
can't fire an unbounded burst of concurrent AI/tool calls.
"""

import asyncio
from types import TracebackType
from typing import Self


class ExecutionPool:
    """An async context manager bounding concurrent step execution to ``max_concurrency``."""

    def __init__(self, max_concurrency: int = 10) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def __aenter__(self) -> Self:
        await self._semaphore.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._semaphore.release()
