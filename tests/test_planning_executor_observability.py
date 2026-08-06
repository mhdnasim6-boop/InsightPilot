"""Tests for PlanExecutor's ExecutionTrace lifecycle: start on execute(), record one
AgentTrace per step from data the (stubbed) orchestration layer already returns, and
finalize on every terminal outcome (COMPLETED/FAILED/CANCELLED). Mirrors
``tests/test_planning_executor.py``'s own ``_StubOrchestrationService`` pattern —
``observability_service`` is exercised as PlanExecutor's optional collaborator, same
as ``approval_service`` before it.
"""

import asyncio

import pytest

from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.observability.exceptions import TraceNotFoundError
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.nodes.approval_node import APPROVAL_NODE_PREFIX
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.executor.executor import PlanExecutor
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


class _StubOrchestrationService:
    """Never pauses (``get_next_nodes()`` always empty) — same stub shape as
    ``tests/test_planning_executor.py``, extended to emit a '<node_name>_result'
    artifact so ObservabilityService has something to build an AgentTrace from.
    """

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[InsightPilotState] = []
        self._fail_on = fail_on

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        self.calls.append(state)
        step_id = state.metadata["step_id"]
        if self._fail_on is not None and step_id == self._fail_on:
            raise RuntimeError(f"simulated failure for step '{self._fail_on}'")
        return state.model_copy(
            update={
                "status": ExecutionStatus.COMPLETED,
                "artifacts": {
                    "sql_agent_result": {
                        "step_id": step_id,
                        "status": "completed",
                        "warnings": [],
                        "execution_time": 0.1,
                        "metadata": {},
                    }
                },
            }
        )

    async def get_next_nodes(self, execution_id: str) -> tuple[str, ...]:
        return ()

    def cancel(self, execution_id: str) -> None:
        pass


def _step(step_id: str) -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name=step_id, node_name="sql_agent")


def _ready_plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id=f"plan-{steps[0].step_id}", created_at=now, updated_at=now, steps=steps, status=PlanStatus.READY)


def test_execute_without_observability_service_behaves_exactly_as_before() -> None:
    async def scenario() -> None:
        executor = PlanExecutor()
        plan = _ready_plan([_step("a")])

        result = await executor.execute(plan, _StubOrchestrationService())  # type: ignore[arg-type]

        assert result.status == PlanStatus.COMPLETED

    asyncio.run(scenario())


def test_execute_starts_and_finalizes_a_completed_trace() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = PlanExecutor(observability_service=observability_service)
        plan = _ready_plan([_step("a")])

        result = await executor.execute(plan, _StubOrchestrationService())  # type: ignore[arg-type]

        assert result.status == PlanStatus.COMPLETED
        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert trace.status == PlanStatus.COMPLETED
        assert trace.end_time is not None
        assert [a.agent_name for a in trace.agent_traces] == ["sql_agent"]

    asyncio.run(scenario())


def test_execute_records_one_agent_trace_per_step() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = PlanExecutor(observability_service=observability_service)
        plan = _ready_plan([_step("a"), _step("b")])

        await executor.execute(plan, _StubOrchestrationService(), execution_order=["a", "b"])  # type: ignore[arg-type]

        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert len(trace.agent_traces) == 2

    asyncio.run(scenario())


def test_execute_failure_finalizes_a_failed_trace_with_the_error_recorded() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = PlanExecutor(observability_service=observability_service)
        plan = _ready_plan([_step("a")])
        stub = _StubOrchestrationService(fail_on="a")

        with pytest.raises(RuntimeError):
            await executor.execute(plan, stub)  # type: ignore[arg-type]

        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert trace.status == PlanStatus.FAILED
        assert any("simulated failure" in error for error in trace.errors)

    asyncio.run(scenario())


class _PausingOrchestrationService:
    """Always pauses at an approval gate — used to reach PlanExecutor's
    ``cancel()`` path, which only accepts a PAUSED (or still-RUNNING) plan.
    """

    def __init__(self) -> None:
        self.cancelled_execution_ids: list[str] = []

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state.model_copy(update={"status": ExecutionStatus.RUNNING})

    async def get_next_nodes(self, execution_id: str) -> tuple[str, ...]:
        return (f"{APPROVAL_NODE_PREFIX}sql_agent",)

    def cancel(self, execution_id: str) -> None:
        self.cancelled_execution_ids.append(execution_id)


def _always_pausing_executor(observability_service: ObservabilityService) -> PlanExecutor:
    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
    approval_policy_service = ApprovalPolicyService()
    approval_policy_service.set_policy(ApprovalPolicy(policy_type=ApprovalPolicyType.ALWAYS))
    return PlanExecutor(
        approval_service=approval_service,
        approval_policy_service=approval_policy_service,
        observability_service=observability_service,
    )


def test_pausing_at_an_approval_gate_marks_the_live_trace_paused() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = _always_pausing_executor(observability_service)
        plan = _ready_plan([_step("a")])

        result = await executor.execute(plan, _PausingOrchestrationService())  # type: ignore[arg-type]

        assert result.status == PlanStatus.PAUSED
        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert trace.status == PlanStatus.PAUSED
        assert trace.end_time is None  # still in progress — not finalized
        assert len(trace.approval_traces) == 1

    asyncio.run(scenario())


def test_cancel_finalizes_a_cancelled_trace() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = _always_pausing_executor(observability_service)
        plan = _ready_plan([_step("a")])
        stub = _PausingOrchestrationService()
        await executor.execute(plan, stub)  # type: ignore[arg-type]

        cancelled = executor.cancel(plan.plan_id, stub)  # type: ignore[arg-type]

        assert cancelled.status == PlanStatus.CANCELLED
        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert trace.status == PlanStatus.CANCELLED
        assert trace.end_time is not None

    asyncio.run(scenario())


def test_reject_finalizes_a_failed_trace() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = _always_pausing_executor(observability_service)
        plan = _ready_plan([_step("a")])
        await executor.execute(plan, _PausingOrchestrationService())  # type: ignore[arg-type]

        rejected = executor.reject(plan.plan_id, reason="too risky")

        assert rejected.status == PlanStatus.FAILED
        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert trace.status == PlanStatus.FAILED
        assert trace.end_time is not None

    asyncio.run(scenario())


def test_finalized_trace_cannot_be_finalized_twice_even_across_executor_calls() -> None:
    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        executor = PlanExecutor(observability_service=observability_service)
        plan = _ready_plan([_step("a")])
        await executor.execute(plan, _StubOrchestrationService())  # type: ignore[arg-type]

        trace_id = observability_service.trace_id_for_plan(plan.plan_id)
        assert trace_id is not None
        with pytest.raises(TraceNotFoundError):
            observability_service.finalize_trace(trace_id, PlanStatus.COMPLETED)

    asyncio.run(scenario())
