"""Tests for JWTService: token creation, decoding, expiration, and clock skew."""

from datetime import datetime

import pytest

from backend.security.authentication.jwt_service import JWTService
from backend.security.authorization.role import Role
from backend.security.exceptions import InvalidTokenError, TokenExpiredError
from backend.security.models.token import TokenType
from backend.security.users.user import User
from backend.utils.time import utc_now

_USER = User(
    user_id="u1", username="alice", email="alice@example.com", full_name="Alice",
    hashed_password="x", role=Role.ANALYST, is_active=True,
    created_at=utc_now(), updated_at=utc_now(),
)


def _service(**overrides: object) -> JWTService:
    defaults: dict[str, object] = {
        "secret_key": "test-secret-key-at-least-32-bytes-long", "algorithm": "HS256",
        "access_expire_minutes": 15, "refresh_expire_minutes": 60, "clock_skew_seconds": 30,
    }
    defaults.update(overrides)
    return JWTService(**defaults)  # type: ignore[arg-type]


def test_create_access_token_has_no_jti() -> None:
    token = _service().create_access_token(_USER)
    claims = _service().decode(token.value, TokenType.ACCESS)
    assert claims.jti is None
    assert claims.sub == "u1"
    assert claims.username == "alice"
    assert claims.role == "analyst"


def test_create_refresh_token_has_a_jti() -> None:
    token = _service().create_refresh_token(_USER)
    claims = _service().decode(token.value, TokenType.REFRESH)
    assert claims.jti is not None


def test_decode_rejects_the_wrong_expected_token_type() -> None:
    service = _service()
    access = service.create_access_token(_USER)
    with pytest.raises(InvalidTokenError):
        service.decode(access.value, TokenType.REFRESH)


def test_decode_rejects_a_token_signed_with_a_different_secret() -> None:
    token = _service(secret_key="a" * 32).create_access_token(_USER)
    with pytest.raises(InvalidTokenError):
        _service(secret_key="b" * 32).decode(token.value, TokenType.ACCESS)


def test_decode_rejects_garbage() -> None:
    with pytest.raises(InvalidTokenError):
        _service().decode("not.a.jwt", TokenType.ACCESS)


def test_expired_token_raises_token_expired_error() -> None:
    service = _service(access_expire_minutes=-1)  # already expired the instant it's issued
    token = service.create_access_token(_USER)
    with pytest.raises(TokenExpiredError):
        service.decode(token.value, TokenType.ACCESS)


def test_clock_skew_leeway_tolerates_a_recently_expired_token() -> None:
    service = _service(access_expire_minutes=-1, clock_skew_seconds=120)
    token = service.create_access_token(_USER)
    claims = service.decode(token.value, TokenType.ACCESS)  # does not raise
    assert claims.sub == "u1"


def test_token_expires_at_is_in_the_future_for_a_normal_token() -> None:
    token = _service().create_access_token(_USER)
    assert token.expires_at > utc_now()


def test_claims_issued_at_and_expires_at_are_datetimes() -> None:
    service = _service()
    token = service.create_refresh_token(_USER)
    claims = service.decode(token.value, TokenType.REFRESH)
    assert isinstance(claims.issued_at, datetime)
    assert isinstance(claims.expires_at, datetime)
    assert claims.expires_at > claims.issued_at
