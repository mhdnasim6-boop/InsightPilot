"""Tests for backend.collaboration.models: shapes, defaults, and immutability."""

from backend.collaboration.models.agent_capability import AgentCapability
from backend.collaboration.models.artifact_exchange import ArtifactExchange
from backend.collaboration.models.collaboration_message import AgentMessage, MessageType
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.models.collaboration_result import CollaborationResult
from backend.collaboration.models.collaboration_statistics import (
    CollaborationStatistics,
)
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.collaboration.models.delegation import Delegation
from backend.collaboration.models.negotiation import NegotiationDecision
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def test_agent_capability_defaults() -> None:
    capability = AgentCapability(name="file_agent")
    assert capability.description == ""
    assert capability.accepted_inputs == []
    assert capability.produced_outputs == []
    assert capability.supported_tools == []
    assert capability.estimated_cost == 0.0
    assert capability.estimated_duration == 0.0


def test_agent_capability_is_frozen() -> None:
    capability = AgentCapability(name="file_agent")
    try:
        capability.name = "sql_agent"  # type: ignore[misc]
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


def test_subtask_defaults_to_pending() -> None:
    subtask = SubTask(subtask_id="st1", description="do work", assigned_agent="file_agent")
    assert subtask.status == NodeStatus.PENDING
    assert subtask.dependencies == []
    assert subtask.result is None
    assert subtask.requested_by is None


def test_collaboration_task_subtask_ids_with_status() -> None:
    now = utc_now()
    subtasks = {
        "a": SubTask(subtask_id="a", description="a", assigned_agent="file_agent", status=NodeStatus.COMPLETED),
        "b": SubTask(subtask_id="b", description="b", assigned_agent="report_agent", status=NodeStatus.PENDING),
    }
    task = CollaborationTask(
        collaboration_id="c1",
        goal="test goal",
        subtasks=subtasks,
        subtask_order=["a", "b"],
        created_at=now,
        updated_at=now,
    )
    assert task.subtask_ids_with_status(NodeStatus.COMPLETED) == ["a"]
    assert task.subtask_ids_with_status(NodeStatus.PENDING) == ["b"]
    assert task.subtask_ids_with_status(NodeStatus.COMPLETED, NodeStatus.PENDING) == ["a", "b"]


def test_collaboration_task_defaults_to_draft() -> None:
    now = utc_now()
    task = CollaborationTask(collaboration_id="c1", goal="test", created_at=now, updated_at=now)
    assert task.status == PlanStatus.DRAFT
    assert task.subtasks == {}
    assert task.active_execution_id is None


def test_delegation_model_shape() -> None:
    delegation = Delegation(
        delegation_id="d1",
        collaboration_id="c1",
        subtask_id="st1",
        from_agent="coordinator",
        to_agent="file_agent",
        reason="initial",
        created_at=utc_now(),
    )
    assert delegation.from_agent == "coordinator"
    assert delegation.to_agent == "file_agent"


def test_agent_message_broadcast_has_no_target() -> None:
    message = AgentMessage(
        message_id="m1",
        collaboration_id="c1",
        from_agent="coordinator",
        to_agent=None,
        message_type=MessageType.ARTIFACT_READY,
        created_at=utc_now(),
    )
    assert message.to_agent is None
    assert message.content == {}


def test_negotiation_decision_shape() -> None:
    decision = NegotiationDecision(
        negotiation_id="n1",
        collaboration_id="c1",
        requested_by=["st1", "st2"],
        resolved_producer_subtask_id="st1",
        reason="identical inputs",
        created_at=utc_now(),
    )
    assert decision.requested_by == ["st1", "st2"]


def test_artifact_exchange_shape() -> None:
    exchange = ArtifactExchange(
        exchange_id="e1",
        collaboration_id="c1",
        producer_subtask_id="st1",
        consumer_subtask_id="st2",
        artifact_keys=["dataset", "analysis_result"],
        created_at=utc_now(),
    )
    assert exchange.artifact_keys == ["dataset", "analysis_result"]


def test_collaboration_request_defaults() -> None:
    request = CollaborationRequest(goal="Analyze sales")
    assert request.session_id is None
    assert request.context == {}


def test_collaboration_result_shape() -> None:
    result = CollaborationResult(
        collaboration_id="c1", goal="Analyze sales", status=PlanStatus.COMPLETED, created_at=utc_now()
    )
    assert result.completed_subtasks == []
    assert result.status == PlanStatus.COMPLETED


def test_collaboration_statistics_defaults() -> None:
    stats = CollaborationStatistics()
    assert stats.total_sessions == 0
    assert stats.by_status == {}
    assert stats.average_subtasks_per_session == 0.0
