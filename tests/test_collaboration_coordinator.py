"""Tests for CollaborationCoordinator: task graph ownership, delegation,
negotiation dedup, spawn_subtask, receive_result, runnable_subtasks,
route_inputs (+ ArtifactExchange recording), and finish.
"""

import pytest

from backend.collaboration.coordinator.artifact_router import ArtifactRouter
from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.coordinator.delegation_engine import DelegationEngine
from backend.collaboration.coordinator.dependency_negotiator import DependencyNegotiator
from backend.collaboration.exceptions import (
    CollaborationNotFoundError,
    SubTaskNotFoundError,
)
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_message import MessageType
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus


def _coordinator() -> tuple[CollaborationCoordinator, CollaborationStore]:
    store = CollaborationStore()
    bus = MessageBus(store)
    coordinator = CollaborationCoordinator(
        store, bus, DelegationEngine(store, bus), DependencyNegotiator(store), ArtifactRouter()
    )
    return coordinator, store


def test_create_session_starts_in_draft_with_no_subtasks() -> None:
    coordinator, _ = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))
    assert task.status == PlanStatus.DRAFT
    assert task.subtasks == {}
    assert task.goal == "Analyze sales"


def test_get_raises_for_unknown_collaboration() -> None:
    coordinator, _ = _coordinator()
    with pytest.raises(CollaborationNotFoundError):
        coordinator.get("missing")


def test_delegate_adds_a_pending_subtask_and_records_a_delegation_message() -> None:
    coordinator, store = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))

    subtask = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {"dataset_reference": "x.csv"})

    updated = coordinator.get(task.collaboration_id)
    assert subtask.subtask_id in updated.subtasks
    assert subtask.status == NodeStatus.PENDING
    assert subtask.assigned_agent == "file_agent"

    delegations = store.list_delegations(task.collaboration_id)
    assert len(delegations) == 1
    assert delegations[0].to_agent == "file_agent"

    messages = store.list_messages(task.collaboration_id)
    assert any(m.message_type == MessageType.DELEGATION_REQUEST for m in messages)


def test_delegate_deduplicates_identical_agent_and_inputs() -> None:
    coordinator, store = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))

    first = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {"dataset_reference": "x.csv"})
    second = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest again", {"dataset_reference": "x.csv"})

    assert first.subtask_id == second.subtask_id
    updated = coordinator.get(task.collaboration_id)
    assert len(updated.subtasks) == 1
    assert len(store.list_negotiations(task.collaboration_id)) == 1


def test_delegate_does_not_deduplicate_different_inputs() -> None:
    coordinator, _ = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))

    first = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest A", {"dataset_reference": "a.csv"})
    second = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest B", {"dataset_reference": "b.csv"})

    assert first.subtask_id != second.subtask_id


def test_spawn_subtask_depends_on_the_requesting_subtask() -> None:
    coordinator, store = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Build a report"))
    report_subtask = coordinator.delegate(task.collaboration_id, "report_agent", "Build report", {})

    followup = coordinator.spawn_subtask(
        task.collaboration_id, report_subtask.subtask_id, "browser_agent", "Get market context",
        inputs={"search_request": "market trends"}, reason="need external context",
    )

    assert followup.dependencies == [report_subtask.subtask_id]
    assert followup.requested_by == report_subtask.subtask_id
    messages = store.list_messages(task.collaboration_id)
    assert any(m.message_type == MessageType.SUBTASK_REQUEST for m in messages)


def test_receive_result_updates_status_and_broadcasts_artifact_ready() -> None:
    coordinator, store = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))
    subtask = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})

    updated_task = coordinator.receive_result(
        task.collaboration_id, subtask.subtask_id, NodeStatus.COMPLETED, {"dataset": {"dataset_id": "d1"}}, None
    )

    assert updated_task.subtasks[subtask.subtask_id].status == NodeStatus.COMPLETED
    assert updated_task.subtasks[subtask.subtask_id].result == {"dataset": {"dataset_id": "d1"}}
    messages = store.list_messages(task.collaboration_id)
    assert any(m.message_type == MessageType.ARTIFACT_READY for m in messages)


def test_receive_result_with_no_result_does_not_broadcast() -> None:
    coordinator, store = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))
    subtask = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})

    coordinator.receive_result(task.collaboration_id, subtask.subtask_id, NodeStatus.FAILED, None, "boom")

    messages = store.list_messages(task.collaboration_id)
    assert not any(m.message_type == MessageType.ARTIFACT_READY for m in messages)


def test_receive_result_raises_for_unknown_subtask() -> None:
    coordinator, _ = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))
    with pytest.raises(SubTaskNotFoundError):
        coordinator.receive_result(task.collaboration_id, "nonexistent", NodeStatus.COMPLETED, None, None)


def test_runnable_subtasks_only_returns_pending_with_satisfied_dependencies() -> None:
    coordinator, _ = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))
    producer = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    consumer = coordinator.delegate(
        task.collaboration_id, "report_agent", "Report", {}, dependencies=[producer.subtask_id]
    )

    task = coordinator.get(task.collaboration_id)
    ready = coordinator.runnable_subtasks(task)
    assert [s.subtask_id for s in ready] == [producer.subtask_id]

    coordinator.receive_result(task.collaboration_id, producer.subtask_id, NodeStatus.COMPLETED, {"dataset": {}}, None)
    task = coordinator.get(task.collaboration_id)
    ready = coordinator.runnable_subtasks(task)
    assert [s.subtask_id for s in ready] == [consumer.subtask_id]


def test_route_inputs_merges_dependency_artifacts_and_records_exchange() -> None:
    coordinator, store = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Pipeline"))
    producer = coordinator.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    consumer = coordinator.delegate(
        task.collaboration_id, "report_agent", "Report", {"report_config": {}}, dependencies=[producer.subtask_id]
    )

    coordinator.receive_result(
        task.collaboration_id, producer.subtask_id, NodeStatus.COMPLETED, {"dataset": {"dataset_id": "d1"}}, None
    )
    task = coordinator.get(task.collaboration_id)

    routed = coordinator.route_inputs(task, task.subtasks[consumer.subtask_id])

    assert routed["dataset"] == {"dataset_id": "d1"}
    assert routed["report_config"] == {}
    exchanges = store.list_exchanges(task.collaboration_id)
    assert len(exchanges) == 1
    assert exchanges[0].producer_subtask_id == producer.subtask_id
    assert exchanges[0].consumer_subtask_id == consumer.subtask_id
    assert "dataset" in exchanges[0].artifact_keys


def test_finish_sets_terminal_status() -> None:
    coordinator, _ = _coordinator()
    task = coordinator.create_session(CollaborationRequest(goal="Analyze sales"))
    finished = coordinator.finish(task.collaboration_id, PlanStatus.COMPLETED)
    assert finished.status == PlanStatus.COMPLETED
