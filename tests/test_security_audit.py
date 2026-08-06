"""Tests for AuditStore and AuditService."""

from backend.security.audit.audit_service import AuditService
from backend.security.audit.audit_store import AuditStore


def _record(service: AuditService, *, user_id: str = "u1", username: str = "alice", status_code: int = 200) -> None:
    service.record(
        user_id=user_id, username=username, action="GET /x", endpoint="/x", method="GET",
        duration_ms=1.5, status_code=status_code, request_id="r1",
    )


def test_record_returns_a_success_event_for_a_2xx_status() -> None:
    service = AuditService(AuditStore())
    event = service.record(
        user_id="u1", username="alice", action="GET /x", endpoint="/x", method="GET",
        duration_ms=2.0, status_code=200, request_id="r1",
    )
    assert event.success is True


def test_record_marks_a_4xx_status_as_a_failure() -> None:
    service = AuditService(AuditStore())
    event = service.record(
        user_id="u1", username="alice", action="GET /x", endpoint="/x", method="GET",
        duration_ms=2.0, status_code=403, request_id="r1",
    )
    assert event.success is False


def test_list_events_is_most_recent_first() -> None:
    service = AuditService(AuditStore())
    _record(service, username="first")
    _record(service, username="second")
    events = service.list_events()
    assert [e.username for e in events] == ["second", "first"]


def test_list_events_respects_limit() -> None:
    service = AuditService(AuditStore())
    for _ in range(5):
        _record(service)
    assert len(service.list_events(limit=2)) == 2


def test_list_events_filters_by_user_id() -> None:
    service = AuditService(AuditStore())
    _record(service, user_id="u1", username="alice")
    _record(service, user_id="u2", username="bob")
    events = service.list_events(user_id="u1")
    assert [e.username for e in events] == ["alice"]


def test_total_events_reflects_every_recorded_event() -> None:
    service = AuditService(AuditStore())
    for _ in range(3):
        _record(service)
    assert service.total_events() == 3


def test_store_caps_at_the_maximum_and_drops_the_oldest() -> None:
    store = AuditStore()
    service = AuditService(store)
    import backend.security.audit.audit_store as audit_store_module

    original_cap = audit_store_module._MAX_EVENTS
    audit_store_module._MAX_EVENTS = 3
    try:
        for i in range(5):
            _record(service, username=f"user{i}")
        assert store.count() == 3
        assert [e.username for e in store.list(limit=10)] == ["user4", "user3", "user2"]
    finally:
        audit_store_module._MAX_EVENTS = original_cap
