"""Tests for CollaborationStore: pure CRUD/append-only storage, keyed by collaboration_id."""

from backend.collaboration.models.artifact_exchange import ArtifactExchange
from backend.collaboration.models.collaboration_message import AgentMessage, MessageType
from backend.collaboration.models.collaboration_result import CollaborationResult
from backend.collaboration.models.collaboration_task import CollaborationTask
from backend.collaboration.models.delegation import Delegation
from backend.collaboration.models.negotiation import NegotiationDecision
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def _task(collaboration_id: str = "c1") -> CollaborationTask:
    now = utc_now()
    return CollaborationTask(collaboration_id=collaboration_id, goal="test", created_at=now, updated_at=now)


def test_put_and_get_task_round_trips() -> None:
    store = CollaborationStore()
    task = _task()
    store.put_task(task)
    assert store.get_task("c1") == task


def test_get_task_returns_none_for_unknown() -> None:
    store = CollaborationStore()
    assert store.get_task("missing") is None


def test_list_tasks_returns_every_task() -> None:
    store = CollaborationStore()
    store.put_task(_task("c1"))
    store.put_task(_task("c2"))
    assert {task.collaboration_id for task in store.list_tasks()} == {"c1", "c2"}


def test_put_task_replaces_wholesale() -> None:
    store = CollaborationStore()
    store.put_task(_task("c1"))
    updated = _task("c1").model_copy(update={"status": PlanStatus.RUNNING})
    store.put_task(updated)
    assert store.get_task("c1").status == PlanStatus.RUNNING  # type: ignore[union-attr]


def test_messages_are_scoped_per_collaboration() -> None:
    store = CollaborationStore()
    message = AgentMessage(
        message_id="m1", collaboration_id="c1", from_agent="coordinator", message_type=MessageType.INFO,
        created_at=utc_now(),
    )
    store.add_message(message)
    assert store.list_messages("c1") == [message]
    assert store.list_messages("c2") == []


def test_delegations_are_scoped_per_collaboration() -> None:
    store = CollaborationStore()
    delegation = Delegation(
        delegation_id="d1", collaboration_id="c1", subtask_id="st1", from_agent="coordinator",
        to_agent="file_agent", reason="", created_at=utc_now(),
    )
    store.add_delegation(delegation)
    assert store.list_delegations("c1") == [delegation]
    assert store.list_delegations("c2") == []


def test_negotiations_are_scoped_per_collaboration() -> None:
    store = CollaborationStore()
    decision = NegotiationDecision(
        negotiation_id="n1", collaboration_id="c1", requested_by=["st1"], resolved_producer_subtask_id="st1",
        reason="", created_at=utc_now(),
    )
    store.add_negotiation(decision)
    assert store.list_negotiations("c1") == [decision]
    assert store.list_negotiations("c2") == []


def test_exchanges_are_scoped_per_collaboration() -> None:
    store = CollaborationStore()
    exchange = ArtifactExchange(
        exchange_id="e1", collaboration_id="c1", producer_subtask_id="st1", consumer_subtask_id="st2",
        created_at=utc_now(),
    )
    store.add_exchange(exchange)
    assert store.list_exchanges("c1") == [exchange]
    assert store.list_exchanges("c2") == []


def test_put_and_get_result_round_trips() -> None:
    store = CollaborationStore()
    result = CollaborationResult(collaboration_id="c1", goal="test", status=PlanStatus.COMPLETED, created_at=utc_now())
    store.put_result(result)
    assert store.get_result("c1") == result
    assert store.get_result("missing") is None


def test_clear_empties_every_collection() -> None:
    store = CollaborationStore()
    store.put_task(_task())
    store.add_message(
        AgentMessage(message_id="m1", collaboration_id="c1", from_agent="x", message_type=MessageType.INFO, created_at=utc_now())
    )
    store.put_result(CollaborationResult(collaboration_id="c1", goal="test", status=PlanStatus.COMPLETED, created_at=utc_now()))

    store.clear()

    assert store.list_tasks() == []
    assert store.list_messages("c1") == []
    assert store.get_result("c1") is None
