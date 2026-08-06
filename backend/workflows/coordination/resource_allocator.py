"""ResourceAllocator: bounds how many *workflows* run concurrently,
process-wide.

A distinct concurrency dimension from ``backend.execution.parallel.execution_pool.ExecutionPool``
(which bounds how many *steps within one execution* run at once) —
this operates one level up, across whole workflow executions. Same
``asyncio.Semaphore``-bounded shape as ``ExecutionPool``, not a
duplicated implementation of anything it does: it is simply reused at a
different scope, exactly like ``NodeStatus`` was a deliberate new
vocabulary next to ``PlanStatus``/``ExecutionStatus`` rather than a
awkward overload of either.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ResourceAllocator:
    """Bounds concurrent workflow executions with an asyncio.Semaphore."""

    def __init__(self, max_concurrent_workflows: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_workflows)
        self._max_concurrent_workflows = max_concurrent_workflows
        self._active = 0

    @property
    def max_concurrent_workflows(self) -> int:
        return self._max_concurrent_workflows

    @property
    def active_count(self) -> int:
        """How many workflow executions currently hold a slot."""
        return self._active

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Hold one concurrency slot for the duration of the ``with`` block."""
        async with self._semaphore:
            self._active += 1
            try:
                yield
            finally:
                self._active -= 1
