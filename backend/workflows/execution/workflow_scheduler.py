"""WorkflowScheduler: bounds and sequences concurrent *workflow*
executions via the existing ResourceAllocator.

A workflow whose ``execute()`` call arrives while every concurrency slot
is already held simply waits — FIFO-fair, via ``asyncio.Semaphore``'s own
built-in waiter queue — until one frees up. No separate queue data
structure is introduced here; it would duplicate what ``asyncio.Semaphore``
(already reused by ``ResourceAllocator``) guarantees on its own.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from backend.workflows.coordination.resource_allocator import ResourceAllocator

T = TypeVar("T")


class WorkflowScheduler:
    """Runs one workflow execution at a time per available ResourceAllocator slot."""

    def __init__(self, resource_allocator: ResourceAllocator) -> None:
        self._resource_allocator = resource_allocator

    async def run(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        """Wait for a concurrency slot, then run ``coro_factory()`` while holding it."""
        async with self._resource_allocator.acquire():
            return await coro_factory()
