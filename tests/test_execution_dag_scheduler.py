"""Tests for DAGScheduler: parallel dispatch of independent steps, retry with
exponential backoff, approval pause/resume without blocking sibling branches,
and cancellation.
"""

import asyncio
import time

from pydantic import BaseModel

from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.scheduler.dependency_resolver import DependencyResolver
from backend.execution.state.execution_state import ExecutionState, StepExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.retry_policy import StepRetryPolicy
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _RecordingService:
    """Records the wall-clock start/end of every call — used to prove concurrency."""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls: list[tuple[str, float, float]] = []

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        start = time.perf_counter()
        await asyncio.sleep(self.delay)
        self.calls.append((step.step_id, start, time.perf_counter()))
        return _Result(step_id=step.step_id)


class _FlakyService:
    """Fails ``fail_times`` times, then succeeds."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.attempts = 0

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise RuntimeError(f"attempt {self.attempts} failed")
        return _Result(step_id=step.step_id)


class _AlwaysFailsService:
    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        raise RuntimeError("always fails")


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", status=PlanStatus.READY, created_at=now, updated_at=now, steps=steps)


def _initial_state(plan: ExecutionPlan) -> ExecutionState:
    now = utc_now()
    return ExecutionState(
        execution_id="e1",
        plan_id=plan.plan_id,
        status=PlanStatus.RUNNING,
        steps={
            step.step_id: StepExecutionState(step_id=step.step_id, node_name=step.node_name) for step in plan.steps
        },
        created_at=now,
        updated_at=now,
    )


def test_independent_steps_execute_concurrently_not_sequentially() -> None:
    """The core proof this phase requires: 3 independent steps with a 0.1s delay
    each finish in ~0.1s total wall time, not ~0.3s — genuine concurrency.
    """

    async def scenario() -> None:
        plan = _plan(
            [
                ExecutionStep(step_id="file", name="File", node_name="file_agent"),
                ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
                ExecutionStep(step_id="browser", name="Browser", node_name="browser_agent"),
            ]
        )
        dispatcher = NodeDispatcher()
        services = {name: _RecordingService(delay=0.1) for name in ("file_agent", "sql_agent", "browser_agent")}
        for name, service in services.items():
            dispatcher.register(name, service)
        scheduler = DAGScheduler(dispatcher)

        start = time.perf_counter()
        state = await scheduler.run(DependencyResolver(plan), _initial_state(plan), session_id=None)
        elapsed = time.perf_counter() - start

        assert state.status == PlanStatus.COMPLETED
        assert elapsed < 0.2  # would be >= 0.3 if dispatched one at a time

        # All three calls overlap in wall-clock time.
        starts = [service.calls[0][1] for service in services.values()]
        ends = [service.calls[0][2] for service in services.values()]
        assert max(starts) < min(ends)

    asyncio.run(scenario())


def test_dependent_step_waits_for_its_dependencies_to_complete() -> None:
    async def scenario() -> None:
        plan = _plan(
            [
                ExecutionStep(step_id="file", name="File", node_name="file_agent"),
                ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
                ExecutionStep(
                    step_id="report", name="Report", node_name="report_agent", dependencies=["file", "sql"]
                ),
            ]
        )
        dispatcher = NodeDispatcher()
        file_service = _RecordingService(delay=0.05)
        sql_service = _RecordingService(delay=0.05)
        report_service = _RecordingService(delay=0.01)
        dispatcher.register("file_agent", file_service)
        dispatcher.register("sql_agent", sql_service)
        dispatcher.register("report_agent", report_service)
        scheduler = DAGScheduler(dispatcher)

        state = await scheduler.run(DependencyResolver(plan), _initial_state(plan), session_id=None)

        assert state.status == PlanStatus.COMPLETED
        report_start = report_service.calls[0][1]
        assert report_start >= file_service.calls[0][2]
        assert report_start >= sql_service.calls[0][2]

    asyncio.run(scenario())


def test_a_failed_step_cancels_only_its_own_dependents() -> None:
    async def scenario() -> None:
        plan = _plan(
            [
                ExecutionStep(step_id="file", name="File", node_name="file_agent"),
                ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
                ExecutionStep(
                    step_id="report", name="Report", node_name="report_agent", dependencies=["file"]
                ),
                ExecutionStep(
                    step_id="summary", name="Summary", node_name="executive_summary_agent", dependencies=["sql"]
                ),
            ]
        )
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _AlwaysFailsService())
        dispatcher.register("sql_agent", _RecordingService())
        dispatcher.register("report_agent", _RecordingService())
        dispatcher.register("executive_summary_agent", _RecordingService())
        scheduler = DAGScheduler(dispatcher)

        state = await scheduler.run(DependencyResolver(plan), _initial_state(plan), session_id=None)

        assert state.status == PlanStatus.FAILED
        assert state.steps["file"].status == NodeStatus.FAILED
        assert state.steps["report"].status == NodeStatus.CANCELLED  # blocked by its failed dependency
        assert state.steps["sql"].status == NodeStatus.COMPLETED  # independent branch unaffected
        assert state.steps["summary"].status == NodeStatus.COMPLETED  # depends on sql, not file

    asyncio.run(scenario())


def test_retry_succeeds_within_max_attempts() -> None:
    async def scenario() -> None:
        step = ExecutionStep(
            step_id="sql",
            name="SQL",
            node_name="sql_agent",
            retry_policy=StepRetryPolicy(max_attempts=3, backoff_seconds=0.01),
        )
        plan = _plan([step])
        dispatcher = NodeDispatcher()
        service = _FlakyService(fail_times=2)
        dispatcher.register("sql_agent", service)
        scheduler = DAGScheduler(dispatcher)

        state = await scheduler.run(DependencyResolver(plan), _initial_state(plan), session_id=None)

        assert state.status == PlanStatus.COMPLETED
        assert state.steps["sql"].status == NodeStatus.COMPLETED
        assert state.steps["sql"].attempts == 3
        assert service.attempts == 3

    asyncio.run(scenario())


def test_retry_gives_up_after_max_attempts_and_marks_failed() -> None:
    async def scenario() -> None:
        step = ExecutionStep(
            step_id="sql",
            name="SQL",
            node_name="sql_agent",
            retry_policy=StepRetryPolicy(max_attempts=2, backoff_seconds=0.0),
        )
        plan = _plan([step])
        dispatcher = NodeDispatcher()
        service = _FlakyService(fail_times=5)
        dispatcher.register("sql_agent", service)
        scheduler = DAGScheduler(dispatcher)

        state = await scheduler.run(DependencyResolver(plan), _initial_state(plan), session_id=None)

        assert state.status == PlanStatus.FAILED
        assert state.steps["sql"].status == NodeStatus.FAILED
        assert state.steps["sql"].attempts == 2
        assert "attempt 2 failed" in (state.steps["sql"].error or "")

    asyncio.run(scenario())


def _approval_collaborators(policy_type: ApprovalPolicyType) -> tuple[ApprovalService, ApprovalPolicyService]:
    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
    approval_policy_service = ApprovalPolicyService()
    approval_policy_service.set_policy(ApprovalPolicy(policy_type=policy_type))
    return approval_service, approval_policy_service


def test_a_gated_step_pauses_while_independent_siblings_keep_running() -> None:
    async def scenario() -> None:
        plan = _plan(
            [
                ExecutionStep(step_id="file", name="File", node_name="file_agent"),
                ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
            ]
        )
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _RecordingService())
        dispatcher.register("sql_agent", _RecordingService())
        approval_service, approval_policy_service = _approval_collaborators(ApprovalPolicyType.ON_SQL)
        scheduler = DAGScheduler(
            dispatcher, approval_service=approval_service, approval_policy_service=approval_policy_service
        )

        state = await scheduler.run(DependencyResolver(plan), _initial_state(plan), session_id=None)

        assert state.status == PlanStatus.PAUSED
        assert state.steps["file"].status == NodeStatus.COMPLETED
        assert state.steps["sql"].status == NodeStatus.PAUSED
        assert len(approval_service.list_pending()) == 1

    asyncio.run(scenario())


def test_resume_after_approval_dispatches_the_previously_paused_step_exactly_once() -> None:
    async def scenario() -> None:
        plan = _plan([ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent")])
        dispatcher = NodeDispatcher()
        service = _RecordingService()
        dispatcher.register("sql_agent", service)
        approval_service, approval_policy_service = _approval_collaborators(ApprovalPolicyType.ON_SQL)
        scheduler = DAGScheduler(
            dispatcher, approval_service=approval_service, approval_policy_service=approval_policy_service
        )
        resolver = DependencyResolver(plan)

        state = await scheduler.run(resolver, _initial_state(plan), session_id=None)
        assert state.status == PlanStatus.PAUSED

        approval = approval_service.list_pending()[0]
        approval_service.approve(approval.approval_id, approver="qa")

        resumed_state = scheduler.resume(resolver, state)
        assert resumed_state.steps["sql"].status == NodeStatus.PENDING
        assert resumed_state.steps["sql"].approved is True

        final_state = await scheduler.run(resolver, resumed_state, session_id=None)
        assert final_state.status == PlanStatus.COMPLETED
        assert len(service.calls) == 1  # never re-dispatched, never re-paused

    asyncio.run(scenario())


def test_resume_after_rejection_cancels_the_step_and_its_dependents() -> None:
    async def scenario() -> None:
        plan = _plan(
            [
                ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
                ExecutionStep(step_id="report", name="Report", node_name="report_agent", dependencies=["sql"]),
            ]
        )
        dispatcher = NodeDispatcher()
        dispatcher.register("sql_agent", _RecordingService())
        dispatcher.register("report_agent", _RecordingService())
        approval_service, approval_policy_service = _approval_collaborators(ApprovalPolicyType.ON_SQL)
        scheduler = DAGScheduler(
            dispatcher, approval_service=approval_service, approval_policy_service=approval_policy_service
        )
        resolver = DependencyResolver(plan)

        state = await scheduler.run(resolver, _initial_state(plan), session_id=None)
        approval = approval_service.list_pending()[0]
        approval_service.reject(approval.approval_id, approver="qa", reason="too risky")

        resumed_state = scheduler.resume(resolver, state)
        final_state = await scheduler.run(resolver, resumed_state, session_id=None)

        assert final_state.status == PlanStatus.FAILED
        assert final_state.steps["sql"].status == NodeStatus.CANCELLED
        assert final_state.steps["report"].status == NodeStatus.CANCELLED

    asyncio.run(scenario())


def test_cancel_stops_non_terminal_steps_and_preserves_completed_ones() -> None:
    plan = _plan(
        [
            ExecutionStep(step_id="file", name="File", node_name="file_agent"),
            ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
        ]
    )
    scheduler = DAGScheduler(NodeDispatcher())
    state = _initial_state(plan)
    state = state.model_copy(
        update={
            "steps": {
                **state.steps,
                "file": state.steps["file"].model_copy(update={"status": NodeStatus.COMPLETED}),
                "sql": state.steps["sql"].model_copy(update={"status": NodeStatus.RUNNING}),
            }
        }
    )

    cancelled = scheduler.cancel(state)

    assert cancelled.status == PlanStatus.CANCELLED
    assert cancelled.steps["file"].status == NodeStatus.COMPLETED
    assert cancelled.steps["sql"].status == NodeStatus.CANCELLED
