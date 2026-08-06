"""EventSerializer: EventEnvelope <-> JSON, for the WebSocket wire and REST responses.

A thin wrapper around pydantic's own ``model_dump_json``/``model_validate_json``
— kept as its own class (rather than calling those methods directly at
each call site) so every serialization boundary (``WebSocketConnection``,
``ReplayService``, tests) goes through one place, matching this
project's "one seam per cross-cutting concern" convention.
"""

from backend.realtime.events.event_envelope import EventEnvelope


class EventSerializer:
    """Serializes/deserializes EventEnvelopes for the WebSocket and REST transports."""

    @staticmethod
    def to_json(envelope: EventEnvelope) -> str:
        """Serialize one envelope to a JSON string."""
        return envelope.model_dump_json()

    @staticmethod
    def to_dict(envelope: EventEnvelope) -> dict:
        """Serialize one envelope to a JSON-safe dict (for ``WebSocket.send_json``)."""
        return envelope.model_dump(mode="json")

    @staticmethod
    def from_json(payload: str) -> EventEnvelope:
        """Deserialize a JSON string back into an EventEnvelope."""
        return EventEnvelope.model_validate_json(payload)
