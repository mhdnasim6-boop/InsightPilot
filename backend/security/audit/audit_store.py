"""AuditStore: process-wide, in-memory audit trail. Append-only — nothing
ever updates or deletes an AuditEvent once recorded.
"""

from backend.security.audit.audit_event import AuditEvent

_MAX_EVENTS = 10_000  # bounds unbounded memory growth in a long-running process; oldest events drop first


class AuditStore:
    """Append-only, capped list of every recorded AuditEvent."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def add(self, event: AuditEvent) -> AuditEvent:
        """Append one event. Drops the oldest event once the cap is reached."""
        self._events.append(event)
        if len(self._events) > _MAX_EVENTS:
            self._events.pop(0)
        return event

    def list(self, limit: int = 100, user_id: str | None = None) -> list[AuditEvent]:
        """Most-recent-first events, optionally filtered to one user, capped at ``limit``."""
        events = self._events if user_id is None else [e for e in self._events if e.user_id == user_id]
        return list(reversed(events))[:limit]

    def count(self) -> int:
        """Total events currently retained (post-cap)."""
        return len(self._events)
