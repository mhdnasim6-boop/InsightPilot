"""Benchmark: sequential (one-step-at-a-time, dependency order) vs parallel
(DAGScheduler) dispatch of the identical ExecutionPlan.

Uses a configurable simulated per-agent delay rather than the real
MockProvider-backed agents — those complete in sub-millisecond time in
this test suite, which would benchmark to pure noise and prove nothing.
A delay of a couple of seconds is representative of what a real AI call,
SQL query, or web search actually costs in production; the comparison
below isolates exactly one variable (parallel vs sequential dispatch of
the same steps through the same ``NodeDispatcher``), deliberately
avoiding any conflation with the *separate*, already-documented
"replays the whole graph every step" inefficiency of the sequential
``PlanExecutor`` path (a different, orthogonal problem this phase
doesn't touch).

Run directly: ``uv run python -m backend.execution.benchmark``
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.scheduler.dependency_resolver import DependencyResolver
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now

_NODE_NAMES = ("file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent")


class _BenchmarkResult(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.0
    warnings: list[str] = []
    metadata: dict[str, Any] = {}


class _SimulatedAgentService:
    """Stands in for a real agent service — sleeps for ``delay`` to simulate realistic latency."""

    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _BenchmarkResult:
        await asyncio.sleep(self._delay)
        return _BenchmarkResult(step_id=step.step_id, execution_time=self._delay)


@dataclass(frozen=True)
class BenchmarkReport:
    """Wall-clock results for one sequential-vs-parallel comparison run."""

    step_count: int
    delay_seconds: float
    sequential_seconds: float
    parallel_seconds: float

    @property
    def speedup(self) -> float:
        """How many times faster the parallel run was."""
        return self.sequential_seconds / self.parallel_seconds if self.parallel_seconds else float("inf")


def build_benchmark_plan() -> ExecutionPlan:
    """A plan mirroring this phase's own worked example: three independent steps
    (File/SQL/Browser) feeding two downstream steps (Report, ExecutiveSummary).
    """
    now = utc_now()
    return ExecutionPlan(
        plan_id="benchmark-plan",
        status=PlanStatus.READY,
        created_at=now,
        updated_at=now,
        steps=[
            ExecutionStep(step_id="file", name="File", node_name="file_agent"),
            ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
            ExecutionStep(step_id="browser", name="Browser", node_name="browser_agent"),
            ExecutionStep(step_id="report", name="Report", node_name="report_agent", dependencies=["file", "sql"]),
            ExecutionStep(
                step_id="exec_summary",
                name="ExecutiveSummary",
                node_name="executive_summary_agent",
                dependencies=["file", "browser"],
            ),
        ],
    )


def _build_dispatcher(delay: float) -> NodeDispatcher:
    dispatcher = NodeDispatcher()
    for node_name in _NODE_NAMES:
        dispatcher.register(node_name, _SimulatedAgentService(delay))
    return dispatcher


async def run_sequential(plan: ExecutionPlan, delay: float) -> float:
    """Today's characterization: one step dispatched at a time, in dependency order."""
    dispatcher = _build_dispatcher(delay)
    resolver = DependencyResolver(plan)
    start = time.perf_counter()
    for step_id in resolver.step_order:
        await dispatcher.dispatch(resolver.step(step_id), None)
    return time.perf_counter() - start


async def run_parallel(plan: ExecutionPlan, delay: float) -> float:
    """The new DAGScheduler: independent steps dispatched concurrently via asyncio.TaskGroup."""
    dispatcher = _build_dispatcher(delay)
    scheduler = DAGScheduler(dispatcher)
    service = ExecutionService(scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry())
    start = time.perf_counter()
    await service.start(plan)
    return time.perf_counter() - start


async def run_benchmark(delay_seconds: float = 2.0) -> BenchmarkReport:
    """Run both engines against the identical plan and report wall-clock results."""
    plan = build_benchmark_plan()
    sequential_seconds = await run_sequential(plan, delay_seconds)
    parallel_seconds = await run_parallel(plan, delay_seconds)
    return BenchmarkReport(
        step_count=len(plan.steps),
        delay_seconds=delay_seconds,
        sequential_seconds=sequential_seconds,
        parallel_seconds=parallel_seconds,
    )


def main() -> None:
    report = asyncio.run(run_benchmark(delay_seconds=2.0))
    print(f"Steps:      {report.step_count} (3 independent -> 2 dependent)")
    print(f"Per-step delay: {report.delay_seconds:.1f}s (simulates a real AI/SQL/web call)")
    print(f"Sequential: {report.sequential_seconds:.1f}s")
    print(f"Parallel:   {report.parallel_seconds:.1f}s")
    print(f"Speedup:    {report.speedup:.2f}x")


if __name__ == "__main__":
    main()
