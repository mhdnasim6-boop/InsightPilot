"""Tests for CollaborationExecutor: drives waves of SubTasks through the real,
unmodified ExecutionService/DAGScheduler — proving independent subtasks in one
wave run concurrently, dependent subtasks run in separate waves with artifacts
routed between them, approval pausing/resuming, cancellation, dynamic
follow-up spawning, and the unreachable-subtask cascade.
"""

import asyncio
import time

import pytest
from pydantic import BaseModel

from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.collaboration.coordinator.artifact_router import ArtifactRouter
from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.coordinator.delegation_engine import DelegationEngine
from backend.collaboration.coordinator.dependency_negotiator import DependencyNegotiator
from backend.collaboration.exceptions import CollaborationNotPausedError
from backend.collaboration.execution.collaboration_executor import CollaborationExecutor
from backend.collaboration.execution.subtask_manager import SubTaskManager
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.step import ExecutionStep


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _RecordingService:
    def __init__(self, delay: float = 0.0, metadata: dict | None = None) -> None:
        self.delay = delay
        self.metadata = metadata or {}
        self.calls: list[tuple[str, float, float]] = []

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        start = time.perf_counter()
        await asyncio.sleep(self.delay)
        self.calls.append((step.step_id, start, time.perf_counter()))
        return _Result(step_id=step.step_id, metadata=self.metadata)


class _DatasetProducingService:
    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        return _Result(step_id=step.step_id, metadata={"dataset": {"dataset_id": "d1"}})


def _stack(dispatcher: NodeDispatcher, approval_service: ApprovalService | None = None, approval_policy_service: ApprovalPolicyService | None = None) -> tuple[CollaborationCoordinator, CollaborationExecutor]:
    store = CollaborationStore()
    bus = MessageBus(store)
    coordinator = CollaborationCoordinator(
        store, bus, DelegationEngine(store, bus), DependencyNegotiator(store), ArtifactRouter()
    )
    scheduler = DAGScheduler(dispatcher, ExecutionPool(), approval_service, approval_policy_service)
    execution_service = ExecutionService(scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry())
    executor = CollaborationExecutor(coordinator, SubTaskManager(coordinator), execution_service)
    return coordinator, executor


def test_independent_subtasks_in_one_wave_execute_concurrently() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        services = {name: _RecordingService(delay=0.1) for name in ("file_agent", "sql_agent", "browser_agent")}
        for name, service in services.items():
            dispatcher.register(name, service)
        coordinator, executor = _stack(dispatcher)

        task = coordinator.create_session(CollaborationRequest(goal="Fan out"))
        for name in services:
            coordinator.delegate(task.collaboration_id, name, f"Run {name}", {})

        start = time.perf_counter()
        final = await executor.run(task.collaboration_id)
        elapsed = time.perf_counter() - start

        assert final.status == PlanStatus.COMPLETED
        assert elapsed < 0.2  # would be >= 0.3 if dispatched one at a time
        starts = [service.calls[0][1] for service in services.values()]
        ends = [service.calls[0][2] for service in services.values()]
        assert max(starts) < min(ends)

    asyncio.run(scenario())


def test_dependent_subtask_runs_in_a_later_wave_with_artifacts_routed() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("file_agent", _DatasetProducingService())
        report_service = _RecordingService()
        dispatcher.register("report_agent", report_service)
        coordinator, executor = _stack(dispatcher)

        task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))
        producer = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})
        coordinator.delegate(
            task.collaboration_id, "report_agent", "Report", {}, dependencies=[producer.subtask_id]
        )

        final = await executor.run(task.collaboration_id)

        assert final.status == PlanStatus.COMPLETED
        assert all(s.status == NodeStatus.COMPLETED for s in final.subtasks.values())

    asyncio.run(scenario())


def test_run_pauses_when_a_subtask_requires_approval_and_resume_continues() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register("sql_agent", _RecordingService())
        approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
        approval_policy_service = ApprovalPolicyService(ApprovalPolicy(policy_type=ApprovalPolicyType.ON_SQL))
        coordinator, executor = _stack(dispatcher, approval_service, approval_policy_service)

        task = coordinator.create_session(CollaborationRequest(goal="Gated"))
        coordinator.delegate(task.collaboration_id, "sql_agent", "Query", {})

        paused = await executor.run(task.collaboration_id)
        assert paused.status == PlanStatus.PAUSED
        assert paused.active_execution_id is not None

        pending = approval_service.list_pending()
        assert len(pending) == 1
        approval_service.approve(pending[0].approval_id, approver="qa")

        resumed = await executor.resume(task.collaboration_id)
        assert resumed.status == PlanStatus.COMPLETED
        assert resumed.active_execution_id is None

    asyncio.run(scenario())


def test_resume_raises_when_not_paused() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        coordinator, executor = _stack(dispatcher)
        task = coordinator.create_session(CollaborationRequest(goal="No subtasks"))

        with pytest.raises(CollaborationNotPausedError):
            await executor.resume(task.collaboration_id)

    asyncio.run(scenario())


def test_cancel_marks_pending_subtasks_cancelled() -> None:
    dispatcher = NodeDispatcher()
    coordinator, executor = _stack(dispatcher)
    task = coordinator.create_session(CollaborationRequest(goal="Never runs"))
    coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})

    cancelled = executor.cancel(task.collaboration_id)

    assert cancelled.status == PlanStatus.CANCELLED
    assert all(s.status == NodeStatus.CANCELLED for s in cancelled.subtasks.values())


def test_dynamic_followup_request_spawns_a_new_subtask() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        dispatcher.register(
            "report_agent",
            _RecordingService(
                metadata={
                    "requested_collaboration": {
                        "agent": "browser_agent",
                        "reason": "need market context",
                        "inputs": {"search_request": "market trends"},
                    }
                }
            ),
        )
        dispatcher.register("browser_agent", _RecordingService())
        coordinator, executor = _stack(dispatcher)

        task = coordinator.create_session(CollaborationRequest(goal="Report with follow-up"))
        coordinator.delegate(task.collaboration_id, "report_agent", "Build report", {})

        final = await executor.run(task.collaboration_id)

        assert final.status == PlanStatus.COMPLETED
        assert len(final.subtasks) == 2
        agents = {s.assigned_agent for s in final.subtasks.values()}
        assert agents == {"report_agent", "browser_agent"}
        browser_subtask = next(s for s in final.subtasks.values() if s.assigned_agent == "browser_agent")
        assert browser_subtask.requested_by is not None

    asyncio.run(scenario())


def test_unreachable_subtask_behind_a_failed_dependency_is_cancelled() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()

        class _AlwaysFails:
            async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
                raise RuntimeError("boom")

        dispatcher.register("file_agent", _AlwaysFails())
        dispatcher.register("report_agent", _RecordingService())
        coordinator, executor = _stack(dispatcher)

        task = coordinator.create_session(CollaborationRequest(goal="Will fail"))
        producer = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})
        coordinator.delegate(
            task.collaboration_id, "report_agent", "Report", {}, dependencies=[producer.subtask_id]
        )

        final = await executor.run(task.collaboration_id)

        assert final.status == PlanStatus.FAILED
        producer_state = final.subtasks[producer.subtask_id]
        assert producer_state.status == NodeStatus.FAILED
        dependent_state = next(s for s in final.subtasks.values() if s.subtask_id != producer.subtask_id)
        assert dependent_state.status == NodeStatus.CANCELLED

    asyncio.run(scenario())
