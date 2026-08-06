"""Tests for backend.realtime.events: Event, EventEnvelope, EventType, EventSerializer."""

import pytest
from pydantic import ValidationError

from backend.realtime.events.event import Event
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_serializer import EventSerializer
from backend.realtime.events.event_type import EventType


def test_event_type_has_exactly_24_members() -> None:
    assert len(list(EventType)) == 24


def test_event_generates_id_and_timestamp_by_default() -> None:
    event = Event(event_type=EventType.WORKFLOW_STARTED)

    assert event.event_id
    assert event.timestamp is not None
    assert event.workflow_id is None
    assert event.data == {}


def test_event_is_frozen() -> None:
    event = Event(event_type=EventType.WORKFLOW_STARTED)

    with pytest.raises(ValidationError):
        event.workflow_id = "w1"  # type: ignore[misc]


def test_event_envelope_round_trips_through_serializer() -> None:
    event = Event(event_type=EventType.STEP_COMPLETED, step_id="s1", agent_name="sql_agent", data={"foo": "bar"})
    envelope = EventEnvelope(sequence=1, event=event)

    payload = EventSerializer.to_json(envelope)
    restored = EventSerializer.from_json(payload)

    assert restored.sequence == 1
    assert restored.event.event_type == EventType.STEP_COMPLETED
    assert restored.event.step_id == "s1"
    assert restored.event.data == {"foo": "bar"}


def test_event_serializer_to_dict_is_json_safe() -> None:
    event = Event(event_type=EventType.USER_LOGGED_IN, user_id="u1")
    envelope = EventEnvelope(sequence=5, event=event)

    payload = EventSerializer.to_dict(envelope)

    assert payload["sequence"] == 5
    assert payload["event"]["event_type"] == "user_logged_in"
    assert isinstance(payload["event"]["timestamp"], str)
