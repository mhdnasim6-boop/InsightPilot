"""Tests for RequestContextMiddleware and AuthenticationMiddleware, against
small throwaway FastAPI apps — isolated from the full backend.main.app so
these stay fast and focus purely on middleware behavior. The full,
real-app integration path is covered separately by
tests/test_api_v1_security.py.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.security.audit.audit_service import AuditService
from backend.security.audit.audit_store import AuditStore
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.authentication.jwt_service import JWTService
from backend.security.authentication.password_hasher import PasswordHasher
from backend.security.authentication.session_manager import SessionManager
from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.policy import default_policy
from backend.security.authorization.role import Role
from backend.security.middleware.authentication import AuthenticationMiddleware
from backend.security.middleware.request_context import (
    RequestContextMiddleware,
    current_request_id,
)
from backend.security.users.user_service import UserService
from backend.security.users.user_store import UserStore


def _auth_stack() -> tuple[AuthenticationService, AuditService, UserService]:
    user_service = UserService(UserStore(), PasswordHasher())
    jwt_service = JWTService(
        secret_key="test-secret-key-at-least-32-bytes-long", algorithm="HS256",
        access_expire_minutes=15, refresh_expire_minutes=60, clock_skew_seconds=30,
    )
    authorization_service = AuthorizationService(default_policy())
    authentication_service = AuthenticationService(
        user_service, jwt_service, SessionManager(), authorization_service
    )
    audit_service = AuditService(AuditStore())
    return authentication_service, audit_service, user_service


def _app_with_auth() -> tuple[FastAPI, AuthenticationService, AuditService, UserService]:
    authentication_service, audit_service, user_service = _auth_stack()
    app = FastAPI()

    @app.get("/whoami")
    def whoami(request: Request) -> dict[str, str | None]:
        user = getattr(request.state, "user", None)
        return {"username": user.username if user else None}

    app.add_middleware(AuthenticationMiddleware, authentication_service=authentication_service, audit_service=audit_service)
    return app, authentication_service, audit_service, user_service


def test_request_context_middleware_generates_a_request_id_header() -> None:
    app = FastAPI()

    @app.get("/x")
    def x() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(RequestContextMiddleware)
    with TestClient(app) as client:
        response = client.get("/x")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_request_context_middleware_echoes_a_caller_supplied_request_id() -> None:
    app = FastAPI()

    @app.get("/x")
    def x() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(RequestContextMiddleware)
    with TestClient(app) as client:
        response = client.get("/x", headers={"X-Request-ID": "caller-supplied-id"})
    assert response.headers["X-Request-ID"] == "caller-supplied-id"


def test_request_context_middleware_sets_the_contextvar_during_the_request() -> None:
    app = FastAPI()
    seen: dict[str, str | None] = {}

    @app.get("/x")
    def x() -> dict[str, bool]:
        seen["id"] = current_request_id.get()
        return {"ok": True}

    app.add_middleware(RequestContextMiddleware)
    with TestClient(app) as client:
        client.get("/x", headers={"X-Request-ID": "abc123"})
    assert seen["id"] == "abc123"
    assert current_request_id.get() is None  # reset after the request


def test_authentication_middleware_attaches_no_user_without_a_token() -> None:
    app, _, _, _ = _app_with_auth()
    with TestClient(app) as client:
        response = client.get("/whoami")
    assert response.json()["username"] is None


def test_authentication_middleware_attaches_the_user_for_a_valid_token() -> None:
    app, authentication_service, _, user_service = _app_with_auth()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = authentication_service.login("alice", "hunter22")

    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": f"Bearer {login_result.access_token}"})

    assert response.json()["username"] == "alice"


def test_authentication_middleware_ignores_an_invalid_token() -> None:
    app, _, _, _ = _app_with_auth()
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.json()["username"] is None


def test_authentication_middleware_ignores_a_non_bearer_header() -> None:
    app, _, _, _ = _app_with_auth()
    with TestClient(app) as client:
        response = client.get("/whoami", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.json()["username"] is None


def test_authentication_middleware_records_no_audit_event_for_an_anonymous_request() -> None:
    app, _, audit_service, _ = _app_with_auth()
    with TestClient(app) as client:
        client.get("/whoami")
    assert audit_service.total_events() == 0


def test_authentication_middleware_records_an_audit_event_for_an_authenticated_request() -> None:
    app, authentication_service, audit_service, user_service = _app_with_auth()
    user_service.create_user("alice", "alice@example.com", "hunter22", Role.ANALYST)
    login_result = authentication_service.login("alice", "hunter22")

    with TestClient(app) as client:
        client.get("/whoami", headers={"Authorization": f"Bearer {login_result.access_token}"})

    events = audit_service.list_events()
    assert len(events) == 1
    assert events[0].username == "alice"
    assert events[0].endpoint == "/whoami"
    assert events[0].success is True
