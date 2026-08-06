"""Tests for ExecutionService: the public entry point wiring DependencyResolver +
DAGScheduler + ExecutionCheckpointStore + ExecutionTaskRegistry + ObservabilityService.
"""

import asyncio

import pytest
from pydantic import BaseModel

from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.exceptions.errors import (
    ExecutionNotFoundError,
    ExecutionNotPausedError,
)
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.execution.state.node_status import NodeStatus
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.planning.exceptions.errors import PlanNotReadyError
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _OkService:
    async def execute_step(self, step, session_id):
        return _Result(step_id=step.step_id)


class _HangingService:
    async def execute_step(self, step, session_id):
        await asyncio.sleep(5)
        return _Result(step_id=step.step_id)


def _plan(steps: list[ExecutionStep], plan_id: str = "p1") -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id=plan_id, status=PlanStatus.READY, created_at=now, updated_at=now, steps=steps)


def _service(dispatcher: NodeDispatcher | None = None, observability: ObservabilityService | None = None) -> tuple[
    ExecutionService, DAGScheduler
]:
    dispatcher = dispatcher or NodeDispatcher()
    scheduler = DAGScheduler(dispatcher, observability_service=observability)
    service = ExecutionService(scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry(), observability)
    return service, scheduler


def test_start_rejects_a_plan_that_is_not_ready() -> None:
    async def scenario() -> None:
        service, _ = _service()
        plan = _plan([ExecutionStep(step_id="a", name="A", node_name="file_agent")]).model_copy(
            update={"status": PlanStatus.DRAFT}
        )
        with pytest.raises(PlanNotReadyError):
            await service.start(plan)

    asyncio.run(scenario())


def test_start_runs_the_dag_to_completion_and_checkpoints_it() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _OkService())
        service, _ = _service(dispatcher)
        plan = _plan([ExecutionStep(step_id="a", name="A", node_name="file_agent")])

        state = await service.start(plan, session_id="s1")

        assert state.status == PlanStatus.COMPLETED
        assert state.steps["a"].status == NodeStatus.COMPLETED
        fetched = service.get(state.execution_id)
        assert fetched == state

    asyncio.run(scenario())


def test_get_raises_for_an_unknown_execution_id() -> None:
    service, _ = _service()
    with pytest.raises(ExecutionNotFoundError):
        service.get("does-not-exist")


def test_get_progress_reflects_completed_steps() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _OkService())
        dispatcher.register("sql_agent", _OkService())
        service, _ = _service(dispatcher)
        plan = _plan(
            [
                ExecutionStep(step_id="a", name="A", node_name="file_agent"),
                ExecutionStep(step_id="b", name="B", node_name="sql_agent"),
            ]
        )

        state = await service.start(plan)
        progress = service.get_progress(state.execution_id)

        assert progress.progress_percent == 100.0
        assert set(progress.completed) == {"a", "b"}

    asyncio.run(scenario())


def test_get_graph_returns_mermaid_with_status_highlighting() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _OkService())
        service, _ = _service(dispatcher)
        plan = _plan([ExecutionStep(step_id="a", name="A", node_name="file_agent")])

        state = await service.start(plan)
        graph = service.get_graph(state.execution_id)

        assert "graph TD;" in graph
        assert "class a completed;" in graph

    asyncio.run(scenario())


def test_get_graph_raises_for_an_unknown_execution_id() -> None:
    service, _ = _service()
    with pytest.raises(ExecutionNotFoundError):
        service.get_graph("does-not-exist")


def test_resume_raises_if_execution_is_not_paused() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _OkService())
        service, _ = _service(dispatcher)
        plan = _plan([ExecutionStep(step_id="a", name="A", node_name="file_agent")])
        state = await service.start(plan)

        with pytest.raises(ExecutionNotPausedError):
            await service.resume(state.execution_id)

    asyncio.run(scenario())


def test_resume_raises_for_an_unknown_execution_id() -> None:
    async def scenario() -> None:
        service, _ = _service()
        with pytest.raises(ExecutionNotPausedError):
            await service.resume("does-not-exist")

    asyncio.run(scenario())


def test_cancel_raises_for_an_unknown_execution_id() -> None:
    service, _ = _service()
    with pytest.raises(ExecutionNotFoundError):
        service.cancel("does-not-exist")


def test_cancel_settles_a_paused_execution_synchronously() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("sql_agent", _OkService())
        approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
        approval_policy_service = ApprovalPolicyService()
        approval_policy_service.set_policy(ApprovalPolicy(policy_type=ApprovalPolicyType.ON_SQL))
        scheduler = DAGScheduler(
            dispatcher, approval_service=approval_service, approval_policy_service=approval_policy_service
        )
        service = ExecutionService(scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry())
        plan = _plan([ExecutionStep(step_id="a", name="A", node_name="sql_agent")])

        state = await service.start(plan)
        assert state.status == PlanStatus.PAUSED

        cancelled = service.cancel(state.execution_id)
        assert cancelled.status == PlanStatus.CANCELLED
        assert cancelled.steps["a"].status == NodeStatus.CANCELLED

    asyncio.run(scenario())


def test_cancel_interrupts_a_genuinely_in_flight_execution() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _OkService())
        dispatcher.register("sql_agent", _HangingService())
        service, _ = _service(dispatcher)
        plan = _plan(
            [
                ExecutionStep(step_id="fast", name="Fast", node_name="file_agent"),
                ExecutionStep(step_id="slow", name="Slow", node_name="sql_agent"),
            ]
        )

        task = asyncio.create_task(service.start(plan))
        await asyncio.sleep(0.2)  # let the fast/slow steps both start dispatching

        # The execution_id is only known once start() returns, which won't
        # happen until this whole DAG settles — poll the same checkpoint
        # store the service was built with to find it while still in flight.
        checkpoint_store = service._checkpoint_store  # test-only introspection
        assert checkpoint_store.list_all(), "expected at least one checkpoint by now"
        execution_id = checkpoint_store.list_all()[0].execution_id

        cancelled = service.cancel(execution_id)
        assert cancelled.status in (PlanStatus.RUNNING, PlanStatus.CANCELLED)

        final_state = await task
        assert final_state.status == PlanStatus.CANCELLED
        assert final_state.steps["fast"].status == NodeStatus.CANCELLED
        assert final_state.steps["slow"].status == NodeStatus.CANCELLED

    asyncio.run(scenario())


def test_full_approval_cycle_records_a_trace_via_observability_service() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("sql_agent", _OkService())
        approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
        approval_policy_service = ApprovalPolicyService()
        approval_policy_service.set_policy(ApprovalPolicy(policy_type=ApprovalPolicyType.ON_SQL))
        observability_service = ObservabilityService(TraceStore())
        scheduler = DAGScheduler(
            dispatcher,
            approval_service=approval_service,
            approval_policy_service=approval_policy_service,
            observability_service=observability_service,
        )
        service = ExecutionService(
            scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry(), observability_service
        )
        plan = _plan([ExecutionStep(step_id="a", name="A", node_name="sql_agent")], plan_id="obs-plan-1")

        state = await service.start(plan)
        assert state.status == PlanStatus.PAUSED

        trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert trace.status == PlanStatus.PAUSED
        assert len(trace.approval_traces) == 1

        approval = approval_service.list_pending()[0]
        approval_service.approve(approval.approval_id, approver="qa")
        final_state = await service.resume(state.execution_id)

        assert final_state.status == PlanStatus.COMPLETED
        finalized_trace = observability_service.get_trace_for_plan(plan.plan_id)
        assert finalized_trace.status == PlanStatus.COMPLETED
        assert len(finalized_trace.agent_traces) == 1
        assert finalized_trace.agent_traces[0].agent_name == "sql_agent"

    asyncio.run(scenario())
