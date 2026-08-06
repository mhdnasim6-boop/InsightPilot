"""Tests for SessionManager: refresh-token session tracking and revocation."""

import pytest

from backend.security.authentication.session_manager import SessionManager
from backend.security.exceptions import TokenRevokedError
from backend.utils.time import utc_now


def test_create_and_require_active_round_trips() -> None:
    manager = SessionManager()
    expires_at = utc_now()
    manager.create("session-1", "user-1", expires_at)
    session = manager.require_active("session-1")
    assert session.user_id == "user-1"
    assert session.revoked is False


def test_require_active_raises_for_an_unknown_session() -> None:
    with pytest.raises(TokenRevokedError):
        SessionManager().require_active("does-not-exist")


def test_revoke_makes_a_session_inactive() -> None:
    manager = SessionManager()
    manager.create("session-1", "user-1", utc_now())
    manager.revoke("session-1")
    with pytest.raises(TokenRevokedError):
        manager.require_active("session-1")


def test_revoke_is_idempotent_for_an_unknown_session() -> None:
    SessionManager().revoke("does-not-exist")  # must not raise


def test_revoke_all_for_user_revokes_only_that_users_sessions() -> None:
    manager = SessionManager()
    manager.create("s1", "user-a", utc_now())
    manager.create("s2", "user-a", utc_now())
    manager.create("s3", "user-b", utc_now())

    manager.revoke_all_for_user("user-a")

    with pytest.raises(TokenRevokedError):
        manager.require_active("s1")
    with pytest.raises(TokenRevokedError):
        manager.require_active("s2")
    manager.require_active("s3")  # untouched


def test_list_active_for_user_excludes_revoked_sessions() -> None:
    manager = SessionManager()
    manager.create("s1", "user-a", utc_now())
    manager.create("s2", "user-a", utc_now())
    manager.revoke("s1")

    active = manager.list_active_for_user("user-a")

    assert [s.session_id for s in active] == ["s2"]
