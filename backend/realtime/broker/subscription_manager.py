"""SubscriptionManager: per-connection event filters and match testing.

Owns no transport (no WebSocket, no send) — ``WebSocketManager`` asks it
"does this connection want this envelope" and does the actual sending
itself. Kept separate so filter logic is independently testable and so
the REST ``GET /subscriptions`` endpoint can inspect it without any
WebSocket machinery in the picture.
"""

from dataclasses import dataclass, field

from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_type import EventType


@dataclass(frozen=True)
class SubscriptionFilter:
    """What one connection wants to see. ``None``/empty on a field means "no restriction"."""

    event_types: frozenset[EventType] = field(default_factory=frozenset)
    workflow_id: str | None = None
    trace_id: str | None = None
    user_id: str | None = None
    agent_name: str | None = None

    def matches(self, envelope: EventEnvelope) -> bool:
        """Whether ``envelope`` satisfies every filter dimension set on this filter."""
        event = envelope.event
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.workflow_id is not None and event.workflow_id != self.workflow_id:
            return False
        if self.trace_id is not None and event.trace_id != self.trace_id:
            return False
        if self.user_id is not None and event.user_id != self.user_id:
            return False
        return not (self.agent_name is not None and event.agent_name != self.agent_name)


class SubscriptionManager:
    """Tracks each connection's current SubscriptionFilter."""

    def __init__(self) -> None:
        self._filters: dict[str, SubscriptionFilter] = {}

    def subscribe(self, connection_id: str, subscription_filter: SubscriptionFilter | None = None) -> None:
        """Register (or replace) ``connection_id``'s filter. No filter means "everything"."""
        self._filters[connection_id] = subscription_filter or SubscriptionFilter()

    def unsubscribe(self, connection_id: str) -> None:
        """Remove ``connection_id``'s filter entirely. A no-op if it has none."""
        self._filters.pop(connection_id, None)

    def filter_for(self, connection_id: str) -> SubscriptionFilter | None:
        """The current filter for ``connection_id``, or ``None`` if not subscribed."""
        return self._filters.get(connection_id)

    def is_subscribed(self, connection_id: str) -> bool:
        """Whether ``connection_id`` currently has an active filter."""
        return connection_id in self._filters

    def matches(self, connection_id: str, envelope: EventEnvelope) -> bool:
        """Whether ``connection_id``'s current filter accepts ``envelope``. False if unsubscribed."""
        subscription_filter = self._filters.get(connection_id)
        if subscription_filter is None:
            return False
        return subscription_filter.matches(envelope)

    def active_connection_ids(self) -> list[str]:
        """Every connection_id currently subscribed, for ``GET /subscriptions``."""
        return list(self._filters.keys())
