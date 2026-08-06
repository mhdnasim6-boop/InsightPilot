"""Tests for SubTaskManager: SubTask <-> ExecutionStep translation, folding
ExecutionState back into the task graph, and the follow-up-request convention.
"""

from backend.collaboration.coordinator.artifact_router import ArtifactRouter
from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.coordinator.delegation_engine import DelegationEngine
from backend.collaboration.coordinator.dependency_negotiator import DependencyNegotiator
from backend.collaboration.execution.subtask_manager import SubTaskManager
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.models.collaboration_task import SubTask
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.execution.state.execution_state import ExecutionState, StepExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def _manager() -> tuple[CollaborationCoordinator, SubTaskManager]:
    store = CollaborationStore()
    bus = MessageBus(store)
    coordinator = CollaborationCoordinator(
        store, bus, DelegationEngine(store, bus), DependencyNegotiator(store), ArtifactRouter()
    )
    return coordinator, SubTaskManager(coordinator)


def test_build_wave_plan_creates_one_step_per_ready_subtask() -> None:
    coordinator, manager = _manager()
    task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))
    subtask = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {"dataset_reference": "x.csv"})
    task = coordinator.get(task.collaboration_id)

    plan = manager.build_wave_plan(task, [subtask], "wave-1")

    assert plan.plan_id == "wave-1"
    assert plan.status == PlanStatus.READY
    assert len(plan.steps) == 1
    assert plan.steps[0].step_id == subtask.subtask_id
    assert plan.steps[0].node_name == "file_agent"
    assert plan.steps[0].inputs == {"dataset_reference": "x.csv"}


def test_build_wave_plan_routes_artifacts_into_step_inputs() -> None:
    coordinator, manager = _manager()
    task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))
    producer = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    coordinator.receive_result(
        task.collaboration_id, producer.subtask_id, NodeStatus.COMPLETED, {"dataset": {"dataset_id": "d1"}}, None
    )
    consumer = coordinator.delegate(
        task.collaboration_id, "report_agent", "Report", {}, dependencies=[producer.subtask_id]
    )
    task = coordinator.get(task.collaboration_id)

    plan = manager.build_wave_plan(task, [task.subtasks[consumer.subtask_id]], "wave-2")

    assert plan.steps[0].inputs["dataset"] == {"dataset_id": "d1"}


def test_apply_execution_state_updates_only_changed_steps() -> None:
    coordinator, manager = _manager()
    task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))
    subtask = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    task = coordinator.get(task.collaboration_id)

    now = utc_now()
    state = ExecutionState(
        execution_id="e1",
        plan_id="wave-1",
        status=PlanStatus.COMPLETED,
        steps={subtask.subtask_id: StepExecutionState(step_id=subtask.subtask_id, node_name="file_agent", status=NodeStatus.COMPLETED, result={"dataset": {}})},
        created_at=now,
        updated_at=now,
    )

    updated_task, settled = manager.apply_execution_state(task.collaboration_id, task, state)

    assert updated_task.subtasks[subtask.subtask_id].status == NodeStatus.COMPLETED
    assert len(settled) == 1
    assert settled[0].subtask_id == subtask.subtask_id


def test_apply_execution_state_ignores_steps_not_in_the_task() -> None:
    coordinator, manager = _manager()
    task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))

    now = utc_now()
    state = ExecutionState(
        execution_id="e1",
        plan_id="wave-1",
        status=PlanStatus.COMPLETED,
        steps={"unrelated-step": StepExecutionState(step_id="unrelated-step", node_name="file_agent", status=NodeStatus.COMPLETED)},
        created_at=now,
        updated_at=now,
    )

    updated_task, settled = manager.apply_execution_state(task.collaboration_id, task, state)

    assert updated_task == task
    assert settled == []


def test_detect_followup_request_reads_the_metadata_convention() -> None:
    _, manager = _manager()
    subtask = SubTask(
        subtask_id="st1",
        description="Build report",
        assigned_agent="report_agent",
        result={"metadata": {"requested_collaboration": {"agent": "browser_agent", "reason": "need context"}}},
    )
    followup = manager.detect_followup_request(subtask)
    assert followup == {"agent": "browser_agent", "reason": "need context"}


def test_detect_followup_request_returns_none_without_the_convention() -> None:
    _, manager = _manager()
    subtask = SubTask(subtask_id="st1", description="Ingest", assigned_agent="file_agent", result={"metadata": {}})
    assert manager.detect_followup_request(subtask) is None


def test_detect_followup_request_returns_none_with_no_result_yet() -> None:
    _, manager = _manager()
    subtask = SubTask(subtask_id="st1", description="Ingest", assigned_agent="file_agent")
    assert manager.detect_followup_request(subtask) is None


def test_detect_followup_request_ignores_malformed_request_missing_agent() -> None:
    _, manager = _manager()
    subtask = SubTask(
        subtask_id="st1", description="Ingest", assigned_agent="file_agent",
        result={"metadata": {"requested_collaboration": {"reason": "no agent key"}}},
    )
    assert manager.detect_followup_request(subtask) is None
