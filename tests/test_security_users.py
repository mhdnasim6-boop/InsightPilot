"""Tests for UserStore and UserService."""

import pytest

from backend.security.authentication.password_hasher import PasswordHasher
from backend.security.authorization.role import Role
from backend.security.exceptions import DuplicateUserError, UserNotFoundError
from backend.security.users.user_service import UserService
from backend.security.users.user_store import UserStore


def _service() -> UserService:
    return UserService(UserStore(), PasswordHasher())


# -- UserStore --------------------------------------------------------------------


def test_store_get_by_username_returns_none_for_unknown() -> None:
    assert UserStore().get_by_username("ghost") is None


def test_store_get_raises_for_unknown_id() -> None:
    with pytest.raises(UserNotFoundError):
        UserStore().get("ghost")


def test_store_delete_raises_for_unknown_id() -> None:
    with pytest.raises(UserNotFoundError):
        UserStore().delete("ghost")


# -- UserService --------------------------------------------------------------------


def test_create_user_can_be_fetched_by_id_and_username() -> None:
    service = _service()
    user = service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    assert service.get(user.user_id).username == "alice"
    assert service.get_by_username("alice").user_id == user.user_id


def test_create_user_rejects_a_duplicate_username() -> None:
    service = _service()
    service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    with pytest.raises(DuplicateUserError):
        service.create_user("alice", "other@example.com", "hunter33", Role.VIEWER)


def test_create_user_hashes_the_password_not_stored_plaintext() -> None:
    service = _service()
    user = service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    assert user.hashed_password != "hunter22"


def test_list_users_returns_profiles_without_hashed_password() -> None:
    service = _service()
    service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    profiles = service.list_users()
    assert len(profiles) == 1
    assert not hasattr(profiles[0], "hashed_password")


def test_update_user_changes_only_given_fields() -> None:
    service = _service()
    user = service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST, full_name="Alice A")
    updated = service.update_user(user.user_id, role=Role.ADMIN)
    assert updated.role == Role.ADMIN
    assert updated.full_name == "Alice A"  # untouched
    assert updated.email == "alice@example.com"  # untouched


def test_update_user_can_change_the_password() -> None:
    service = _service()
    user = service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    service.update_user(user.user_id, password="newpassword1")
    assert service.verify_credentials("alice", "newpassword1") is not None
    assert service.verify_credentials("alice", "hunter22") is None


def test_delete_user_removes_it() -> None:
    service = _service()
    user = service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    service.delete_user(user.user_id)
    with pytest.raises(UserNotFoundError):
        service.get(user.user_id)


def test_verify_credentials_returns_none_for_unknown_username() -> None:
    assert _service().verify_credentials("ghost", "whatever") is None


def test_verify_credentials_returns_none_for_wrong_password() -> None:
    service = _service()
    service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    assert service.verify_credentials("alice", "wrong-password") is None


def test_verify_credentials_returns_none_for_an_inactive_account() -> None:
    service = _service()
    user = service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    service.update_user(user.user_id, is_active=False)
    assert service.verify_credentials("alice", "hunter22") is None


def test_verify_credentials_returns_the_user_for_correct_credentials() -> None:
    service = _service()
    service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    user = service.verify_credentials("alice", "hunter22")
    assert user is not None
    assert user.username == "alice"


def test_ensure_default_admin_creates_exactly_one_admin_on_a_fresh_store() -> None:
    service = _service()
    service.ensure_default_admin("admin", "ChangeMe123!")
    users = service.list_users()
    assert len(users) == 1
    assert users[0].username == "admin"
    assert users[0].role == Role.ADMIN


def test_ensure_default_admin_is_idempotent_once_any_user_exists() -> None:
    service = _service()
    service.create_user("bob", "bob@example.com", "hunter22", Role.VIEWER)
    service.ensure_default_admin("admin", "ChangeMe123!")
    usernames = {u.username for u in service.list_users()}
    assert usernames == {"bob"}  # no admin bootstrapped — a user already existed
