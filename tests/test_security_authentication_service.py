"""Tests for AuthenticationService: login, logout, refresh (with rotation),
and access-token verification — built from real (not mocked) collaborators.
"""

import pytest

from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.authentication.jwt_service import JWTService
from backend.security.authentication.password_hasher import PasswordHasher
from backend.security.authentication.session_manager import SessionManager
from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.permission import Permission
from backend.security.authorization.policy import default_policy
from backend.security.authorization.role import Role
from backend.security.exceptions import (
    AccountDisabledError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)
from backend.security.users.user_service import UserService
from backend.security.users.user_store import UserStore


def _service(**jwt_overrides: object) -> tuple[AuthenticationService, UserService]:
    user_service = UserService(UserStore(), PasswordHasher())
    jwt_defaults: dict[str, object] = {
        "secret_key": "test-secret-key-at-least-32-bytes-long", "algorithm": "HS256",
        "access_expire_minutes": 15, "refresh_expire_minutes": 60, "clock_skew_seconds": 30,
    }
    jwt_defaults.update(jwt_overrides)
    jwt_service = JWTService(**jwt_defaults)  # type: ignore[arg-type]
    session_manager = SessionManager()
    authorization_service = AuthorizationService(default_policy())
    auth_service = AuthenticationService(user_service, jwt_service, session_manager, authorization_service)
    return auth_service, user_service


def test_login_succeeds_with_correct_credentials() -> None:
    auth_service, user_service = _service()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)

    result = auth_service.login("alice", "hunter22")

    assert result.user.username == "alice"
    assert result.token_type == "bearer"
    assert result.access_token and result.refresh_token


def test_login_raises_invalid_credentials_for_unknown_username() -> None:
    auth_service, _ = _service()
    with pytest.raises(InvalidCredentialsError):
        auth_service.login("ghost", "whatever")


def test_login_raises_invalid_credentials_for_wrong_password() -> None:
    auth_service, user_service = _service()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    with pytest.raises(InvalidCredentialsError):
        auth_service.login("alice", "wrong-password")


def test_authenticate_returns_the_users_current_permissions() -> None:
    auth_service, user_service = _service()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = auth_service.login("alice", "hunter22")

    authenticated = auth_service.authenticate(login_result.access_token)

    assert authenticated.username == "alice"
    assert authenticated.role == Role.ANALYST
    assert Permission.RUN_ANALYSIS in authenticated.permissions
    assert Permission.MANAGE_USERS not in authenticated.permissions


def test_authenticate_raises_for_an_expired_access_token() -> None:
    auth_service, user_service = _service(access_expire_minutes=-1)
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = auth_service.login("alice", "hunter22")
    with pytest.raises(TokenExpiredError):
        auth_service.authenticate(login_result.access_token)


def test_authenticate_rejects_a_refresh_token_used_as_an_access_token() -> None:
    auth_service, user_service = _service()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = auth_service.login("alice", "hunter22")
    with pytest.raises(InvalidTokenError):
        auth_service.authenticate(login_result.refresh_token)


def test_logout_revokes_the_refresh_tokens_session() -> None:
    auth_service, user_service = _service()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = auth_service.login("alice", "hunter22")

    auth_service.logout(login_result.refresh_token)

    with pytest.raises(TokenRevokedError):
        auth_service.refresh(login_result.refresh_token)


def test_refresh_issues_a_new_pair_and_revokes_the_old_session() -> None:
    auth_service, user_service = _service()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = auth_service.login("alice", "hunter22")

    refreshed = auth_service.refresh(login_result.refresh_token)

    # refresh_token always differs — each carries its own unique jti (session id).
    # access_token is NOT asserted here: two access tokens issued for the same user
    # within the same integer second carry byte-identical claims (no jti on access
    # tokens by design — see JWTService's own docstring) and are legitimately
    # identical strings; that's not a security issue, just second-granularity iat/exp.
    assert refreshed.refresh_token != login_result.refresh_token
    with pytest.raises(TokenRevokedError):
        auth_service.refresh(login_result.refresh_token)  # old refresh token is now dead


def test_refresh_raises_for_an_account_deactivated_since_login() -> None:
    auth_service, user_service = _service()
    user = user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = auth_service.login("alice", "hunter22")
    user_service.update_user(user.user_id, is_active=False)

    with pytest.raises(AccountDisabledError):
        auth_service.refresh(login_result.refresh_token)
