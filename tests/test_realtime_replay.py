"""Tests for backend.realtime.replay: ReplayBuffer and ReplayService."""

from datetime import timedelta

import pytest

from backend.realtime.broker.subscription_manager import SubscriptionFilter
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.exceptions import InvalidReplayRequestError
from backend.realtime.replay.replay_buffer import ReplayBuffer
from backend.realtime.replay.replay_service import ReplayService
from backend.utils.time import utc_now


def _fill(buffer: ReplayBuffer, count: int, event_type: EventType = EventType.WORKFLOW_STARTED) -> None:
    for _ in range(count):
        buffer.append(buffer.make_event_envelope(Event(event_type=event_type)))


def test_replay_buffer_next_sequence_is_monotonic() -> None:
    buffer = ReplayBuffer()
    assert buffer.next_sequence() == 1
    assert buffer.next_sequence() == 2
    assert buffer.next_sequence() == 3


def test_replay_buffer_evicts_oldest_at_capacity() -> None:
    buffer = ReplayBuffer(capacity=3)
    _fill(buffer, 5)

    envelopes = buffer.all()

    assert len(envelopes) == 3
    assert [e.sequence for e in envelopes] == [3, 4, 5]


def test_replay_buffer_last_returns_most_recent() -> None:
    buffer = ReplayBuffer(capacity=10)
    _fill(buffer, 5)

    last_two = buffer.last(2)

    assert [e.sequence for e in last_two] == [4, 5]


def test_replay_buffer_last_with_zero_or_negative_returns_empty() -> None:
    buffer = ReplayBuffer()
    _fill(buffer, 3)
    assert buffer.last(0) == []
    assert buffer.last(-1) == []


def test_replay_buffer_since_filters_by_published_at() -> None:
    buffer = ReplayBuffer()
    _fill(buffer, 2)
    cutoff = utc_now()
    _fill(buffer, 2)

    recent = buffer.since(cutoff)

    assert len(recent) == 2
    assert all(e.published_at > cutoff for e in recent)


def test_replay_service_defaults_to_whole_buffer() -> None:
    buffer = ReplayBuffer()
    _fill(buffer, 4)
    service = ReplayService(buffer)

    assert len(service.replay()) == 4


def test_replay_service_count_and_since_are_mutually_exclusive() -> None:
    buffer = ReplayBuffer()
    service = ReplayService(buffer)

    with pytest.raises(InvalidReplayRequestError):
        service.replay(count=10, since=utc_now())


def test_replay_service_applies_subscription_filter() -> None:
    buffer = ReplayBuffer()
    buffer.append(buffer.make_event_envelope(Event(event_type=EventType.WORKFLOW_STARTED)))
    buffer.append(buffer.make_event_envelope(Event(event_type=EventType.TOOL_STARTED)))
    service = ReplayService(buffer)

    matched = service.replay(subscription_filter=SubscriptionFilter(event_types=frozenset({EventType.TOOL_STARTED})))

    assert len(matched) == 1
    assert matched[0].event.event_type == EventType.TOOL_STARTED


def test_replay_service_since_excludes_events_before_cutoff() -> None:
    buffer = ReplayBuffer()
    _fill(buffer, 2)
    cutoff = utc_now() + timedelta(seconds=1)

    service = ReplayService(buffer)
    assert service.replay(since=cutoff) == []
