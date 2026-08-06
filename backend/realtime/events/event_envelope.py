"""EventEnvelope: the transport wrapper around one Event.

Adds what only the *transport* layer cares about — a global, monotonic
``sequence`` (what the replay buffer orders and paginates by) and
``published_at`` (when ``RealtimeService`` actually published it, as
opposed to ``Event.timestamp``, which is when the underlying subsystem
fact occurred; normally identical, but kept distinct so a future
buffered/delayed publisher can't corrupt replay ordering).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.realtime.events.event import Event
from backend.utils.time import utc_now


class EventEnvelope(BaseModel):
    """One sequenced, transport-ready Event."""

    model_config = ConfigDict(frozen=True)

    sequence: int
    event: Event
    published_at: datetime = Field(default_factory=utc_now)
