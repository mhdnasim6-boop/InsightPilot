"""ReplayService: filtered replay queries over a ReplayBuffer.

Shared by both transports that offer replay — ``GET /api/v1/realtime/replay``
and the WebSocket ``replay`` action — so filter semantics (last N,
since a timestamp, or the whole buffer, each optionally narrowed by the
same dimensions ``SubscriptionFilter`` uses) live in exactly one place.
"""

from datetime import datetime

from backend.realtime.broker.subscription_manager import SubscriptionFilter
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.exceptions import InvalidReplayRequestError
from backend.realtime.replay.replay_buffer import ReplayBuffer


class ReplayService:
    """Answers "what happened" queries against a ReplayBuffer."""

    def __init__(self, replay_buffer: ReplayBuffer) -> None:
        self._replay_buffer = replay_buffer

    def replay(
        self,
        count: int | None = None,
        since: datetime | None = None,
        subscription_filter: SubscriptionFilter | None = None,
    ) -> list[EventEnvelope]:
        """Return matching envelopes, oldest first.

        Exactly one of ``count``/``since`` may be given (they express
        mutually exclusive "how much history" requests); neither means
        "the whole buffer." Raises InvalidReplayRequestError if both are given.
        """
        if count is not None and since is not None:
            raise InvalidReplayRequestError("Pass either 'count' or 'since', not both.")

        if count is not None:
            envelopes = self._replay_buffer.last(count)
        elif since is not None:
            envelopes = self._replay_buffer.since(since)
        else:
            envelopes = self._replay_buffer.all()

        if subscription_filter is None:
            return envelopes
        return [envelope for envelope in envelopes if subscription_filter.matches(envelope)]
