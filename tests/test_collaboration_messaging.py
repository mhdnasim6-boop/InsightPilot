"""Tests for MessageBus/Inbox/Outbox: the only channel agents/coordinator communicate through."""

from backend.collaboration.messaging.inbox import Inbox
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.messaging.outbox import Outbox
from backend.collaboration.models.collaboration_message import MessageType
from backend.collaboration.stores.collaboration_store import CollaborationStore


def test_send_persists_and_is_returned_by_history() -> None:
    bus = MessageBus(CollaborationStore())
    message = bus.send("c1", "coordinator", "file_agent", MessageType.DELEGATION_REQUEST, {"subtask_id": "st1"})

    assert message.from_agent == "coordinator"
    assert message.to_agent == "file_agent"
    assert bus.history("c1") == [message]


def test_broadcast_has_no_target_agent() -> None:
    bus = MessageBus(CollaborationStore())
    message = bus.broadcast("c1", "file_agent", MessageType.ARTIFACT_READY)
    assert message.to_agent is None


def test_receive_returns_direct_and_broadcast_messages_only() -> None:
    bus = MessageBus(CollaborationStore())
    direct = bus.send("c1", "coordinator", "report_agent", MessageType.DELEGATION_REQUEST)
    broadcast = bus.broadcast("c1", "file_agent", MessageType.ARTIFACT_READY)
    bus.send("c1", "coordinator", "browser_agent", MessageType.DELEGATION_REQUEST)  # addressed elsewhere

    received = bus.receive("c1", "report_agent")

    assert received == [direct, broadcast]


def test_receive_is_scoped_per_collaboration() -> None:
    bus = MessageBus(CollaborationStore())
    bus.send("c1", "coordinator", "file_agent", MessageType.DELEGATION_REQUEST)
    assert bus.receive("c2", "file_agent") == []


def test_history_returns_every_message_in_send_order() -> None:
    bus = MessageBus(CollaborationStore())
    first = bus.send("c1", "coordinator", "file_agent", MessageType.DELEGATION_REQUEST)
    second = bus.broadcast("c1", "file_agent", MessageType.ARTIFACT_READY)
    assert bus.history("c1") == [first, second]


def test_inbox_scopes_receive_to_one_agent() -> None:
    bus = MessageBus(CollaborationStore())
    bus.send("c1", "coordinator", "report_agent", MessageType.DELEGATION_REQUEST)
    inbox = Inbox(bus, "report_agent")
    assert len(inbox.messages("c1")) == 1


def test_outbox_scopes_send_to_one_agent_as_sender() -> None:
    bus = MessageBus(CollaborationStore())
    outbox = Outbox(bus, "report_agent")
    message = outbox.send("c1", "browser_agent", MessageType.SUBTASK_REQUEST, {"reason": "need context"})
    assert message.from_agent == "report_agent"
    assert message.to_agent == "browser_agent"


def test_outbox_broadcast_sets_from_agent() -> None:
    bus = MessageBus(CollaborationStore())
    outbox = Outbox(bus, "file_agent")
    message = outbox.broadcast("c1", MessageType.ARTIFACT_READY)
    assert message.from_agent == "file_agent"
    assert message.to_agent is None
