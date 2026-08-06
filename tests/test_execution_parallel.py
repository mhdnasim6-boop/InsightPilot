"""Tests for ExecutionPool (concurrency bound) and run_concurrently() (asyncio.TaskGroup fan-out)."""

import asyncio

import pytest

from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.parallel.task_group import run_concurrently


def test_run_concurrently_returns_results_in_input_order() -> None:
    async def scenario() -> None:
        async def worker(value: int, delay: float) -> int:
            await asyncio.sleep(delay)
            return value

        results = await run_concurrently([worker(1, 0.03), worker(2, 0.01), worker(3, 0.02)])

        assert results == [1, 2, 3]

    asyncio.run(scenario())


def test_run_concurrently_with_no_coroutines_returns_empty_list() -> None:
    async def scenario() -> list[int]:
        return await run_concurrently([])

    assert asyncio.run(scenario()) == []


def test_run_concurrently_executes_genuinely_in_parallel_not_sequentially() -> None:
    async def scenario() -> float:
        async def worker() -> None:
            await asyncio.sleep(0.1)

        import time

        start = time.perf_counter()
        await run_concurrently([worker(), worker(), worker()])
        return time.perf_counter() - start

    elapsed = asyncio.run(scenario())
    # Three 0.1s sleeps run concurrently should take ~0.1s, not ~0.3s.
    assert elapsed < 0.2


def test_execution_pool_bounds_concurrent_entries() -> None:
    async def scenario() -> int:
        pool = ExecutionPool(max_concurrency=2)
        concurrent = 0
        max_concurrent = 0

        async def worker() -> None:
            nonlocal concurrent, max_concurrent
            async with pool:
                concurrent += 1
                max_concurrent = max(max_concurrent, concurrent)
                await asyncio.sleep(0.05)
                concurrent -= 1

        await asyncio.gather(*(worker() for _ in range(6)))
        return max_concurrent

    assert asyncio.run(scenario()) == 2


def test_execution_pool_allows_full_concurrency_within_its_limit() -> None:
    async def scenario() -> int:
        pool = ExecutionPool(max_concurrency=5)
        concurrent = 0
        max_concurrent = 0

        async def worker() -> None:
            nonlocal concurrent, max_concurrent
            async with pool:
                concurrent += 1
                max_concurrent = max(max_concurrent, concurrent)
                await asyncio.sleep(0.03)
                concurrent -= 1

        await asyncio.gather(*(worker() for _ in range(3)))
        return max_concurrent

    assert asyncio.run(scenario()) == 3


def test_run_concurrently_isolates_a_raising_coroutine_from_the_taskgroup_caller() -> None:
    """A coroutine passed to run_concurrently is expected to never raise (per its own
    docstring contract) — DAGScheduler enforces this by catching everything inside its
    own per-step wrapper. This test documents that an uncaught exception here still
    propagates via TaskGroup's ExceptionGroup, i.e. run_concurrently itself adds no
    extra safety net — that responsibility belongs entirely to the caller.
    """

    async def scenario() -> None:
        async def ok() -> int:
            await asyncio.sleep(0.02)
            return 1

        async def bad() -> int:
            raise RuntimeError("boom")

        with pytest.raises(ExceptionGroup):
            await run_concurrently([ok(), bad()])

    asyncio.run(scenario())
