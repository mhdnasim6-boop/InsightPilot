"""ReplayBuffer: a bounded, in-memory, append-only store of every published
EventEnvelope, plus this package's own monotonic sequence counter.

Bounded via ``collections.deque(maxlen=...)`` rather than an unbounded
list — a long-running process must not accumulate every event ever
published; "configurable" (per this phase's own requirement) means the
constructor's own ``capacity`` argument, not a hardcoded constant.
"""

from collections import deque
from datetime import datetime

from backend.realtime.events.event import Event
from backend.realtime.events.event_envelope import EventEnvelope

DEFAULT_CAPACITY = 1000


class ReplayBuffer:
    """Bounded, sequence-ordered store of recently published EventEnvelopes."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._capacity = capacity
        self._envelopes: deque[EventEnvelope] = deque(maxlen=capacity)
        self._sequence = 0

    @property
    def capacity(self) -> int:
        """The maximum number of envelopes this buffer retains."""
        return self._capacity

    def next_sequence(self) -> int:
        """Allocate and return the next monotonic sequence number."""
        self._sequence += 1
        return self._sequence

    def append(self, envelope: EventEnvelope) -> None:
        """Store ``envelope``, evicting the oldest one if at capacity."""
        self._envelopes.append(envelope)

    def all(self) -> list[EventEnvelope]:
        """Every currently retained envelope, oldest first."""
        return list(self._envelopes)

    def last(self, count: int) -> list[EventEnvelope]:
        """The most recent ``count`` envelopes, oldest first."""
        if count <= 0:
            return []
        envelopes = self._envelopes
        return list(envelopes)[-count:]

    def since(self, timestamp: datetime) -> list[EventEnvelope]:
        """Every envelope published strictly after ``timestamp``, oldest first."""
        return [envelope for envelope in self._envelopes if envelope.published_at > timestamp]

    def make_event_envelope(self, event: Event) -> EventEnvelope:
        """Build the next sequenced envelope for ``event`` without storing it."""
        return EventEnvelope(sequence=self.next_sequence(), event=event)
