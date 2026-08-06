"""AuditService: the only public entry point for recording/reading audit
events. Reusable by design — the one caller today is
``backend.security.middleware.authentication.AuthenticationMiddleware``,
but recording an event never requires anything beyond the plain values
this service's ``record()`` method already takes, so any future caller
(a future admin action, a plugin lifecycle event) can reuse it with zero
changes here.
"""

from backend.security.audit.audit_event import AuditEvent
from backend.security.audit.audit_store import AuditStore
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class AuditService:
    """Records and queries the audit trail."""

    def __init__(self, store: AuditStore) -> None:
        self._store = store

    def record(
        self, *, user_id: str, username: str, action: str, endpoint: str, method: str,
        duration_ms: float, status_code: int, request_id: str,
    ) -> AuditEvent:
        """Record one audit event. ``success`` is derived from ``status_code`` (< 400), never passed in."""
        event = AuditEvent(
            audit_id=generate_id(), timestamp=utc_now(), user_id=user_id, username=username,
            action=action, endpoint=endpoint, method=method, duration_ms=duration_ms,
            status_code=status_code, success=status_code < 400, request_id=request_id,
        )
        return self._store.add(event)

    def list_events(self, limit: int = 100, user_id: str | None = None) -> list[AuditEvent]:
        """Most-recent-first audit events, optionally scoped to one user."""
        return self._store.list(limit=limit, user_id=user_id)

    def total_events(self) -> int:
        """Total events currently retained."""
        return self._store.count()
