"""Tests for the sequential-vs-parallel benchmark — using a small delay so
these stay fast, but still prove the DAG engine dispatches independent
steps concurrently rather than one at a time.
"""

import asyncio

from backend.execution.benchmark import (
    build_benchmark_plan,
    run_benchmark,
    run_parallel,
    run_sequential,
)


def test_parallel_is_meaningfully_faster_than_sequential() -> None:
    report = asyncio.run(run_benchmark(delay_seconds=0.1))

    assert report.step_count == 5
    # Sequential dispatches all 5 steps one at a time: ~5 * delay.
    assert report.sequential_seconds >= 0.4
    # Parallel dispatches in two batches (3 independent, then 2 dependent): ~2 * delay.
    assert report.parallel_seconds < report.sequential_seconds / 2
    assert report.speedup > 1.8


def test_parallel_wall_time_matches_batch_count_not_step_count() -> None:
    """3 independent steps + 2 dependent steps -> 2 batches, not 5 sequential slots."""
    plan = build_benchmark_plan()
    delay = 0.1

    parallel_seconds = asyncio.run(run_parallel(plan, delay))

    # Roughly 2 * delay (two dependency layers), with generous slack for
    # scheduling/event-loop overhead — well short of 5 * delay either way.
    assert delay * 1.5 < parallel_seconds < delay * 3.5


def test_sequential_wall_time_scales_with_step_count() -> None:
    plan = build_benchmark_plan()
    delay = 0.1

    sequential_seconds = asyncio.run(run_sequential(plan, delay))

    assert sequential_seconds >= len(plan.steps) * delay * 0.9
