"""run_concurrently(): executes a batch of coroutines concurrently via asyncio.TaskGroup.

Every coroutine passed in is expected to catch its own exceptions
internally (``DAGScheduler``'s own node-dispatch wrapper does exactly
this) — ``TaskGroup`` cancels every sibling task the instant one raises,
which would silently undermine "one branch's failure must never affect
an independent branch." Nothing passed to this function is allowed to
raise; it exists purely to fan out real concurrency, not to add its own
error-isolation policy.
"""

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any, TypeVar

T = TypeVar("T")


async def run_concurrently(coroutines: Sequence[Coroutine[Any, Any, T]]) -> list[T]:
    """Run every coroutine in ``coroutines`` concurrently, returning their results in order."""
    if not coroutines:
        return []
    tasks: list[asyncio.Task[T]] = []
    async with asyncio.TaskGroup() as task_group:
        for coroutine in coroutines:
            tasks.append(task_group.create_task(coroutine))
    return [task.result() for task in tasks]
