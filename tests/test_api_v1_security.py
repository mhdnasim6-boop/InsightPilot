"""Tests for the /api/v1/{login,logout,refresh-token,me,users,audit,roles,
permissions} endpoints against the real app, with the real default admin
account genuinely seeded via lifespan/create_app() — mirrors every other
REST test file's own "exercise the real thing" pattern.

Every test that creates a user uses a unique username (via ``uuid4``) —
UserStore is a process-wide singleton shared across the whole test
session (like ToolRegistry/PluginRegistry before it), so a fixed
username would collide across test runs/files.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.main import app

_ADMIN_USERNAME = "admin"
_ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _unique_username(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_login_with_the_seeded_admin_account_succeeds(client: TestClient) -> None:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["user"]["username"] == _ADMIN_USERNAME
    assert data["user"]["role"] == "admin"
    assert data["access_token"] and data["refresh_token"]


def test_login_with_wrong_password_returns_401(client: TestClient) -> None:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": "wrong"})
    assert response.status_code == 401


def test_login_with_unknown_username_returns_401(client: TestClient) -> None:
    response = client.post("/api/v1/login", json={"username": "does-not-exist", "password": "whatever"})
    assert response.status_code == 401


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_me_returns_the_current_users_profile(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["username"] == _ADMIN_USERNAME


def test_me_rejects_an_invalid_token(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_admin_can_list_users(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 200, response.text
    assert any(u["username"] == _ADMIN_USERNAME for u in response.json()["data"])


def test_admin_can_create_a_user(client: TestClient) -> None:
    headers = _admin_headers(client)
    username = _unique_username("analyst")
    response = client.post(
        "/api/v1/users", headers=headers,
        json={"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "analyst"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["role"] == "analyst"


def test_a_viewer_cannot_manage_users(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    username = _unique_username("viewer")
    client.post(
        "/api/v1/users", headers=admin_headers,
        json={"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "viewer"},
    )
    login = client.post("/api/v1/login", json={"username": username, "password": "Password123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    response = client.get("/api/v1/users", headers=viewer_headers)

    assert response.status_code == 403


def test_admin_can_update_and_delete_a_user(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    username = _unique_username("temp")
    created = client.post(
        "/api/v1/users", headers=admin_headers,
        json={"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "viewer"},
    ).json()["data"]

    updated = client.put(
        f"/api/v1/users/{created['user_id']}", headers=admin_headers, json={"role": "analyst"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["role"] == "analyst"

    deleted = client.delete(f"/api/v1/users/{created['user_id']}", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text

    missing = client.put(f"/api/v1/users/{created['user_id']}", headers=admin_headers, json={"role": "viewer"})
    assert missing.status_code == 404


def test_create_user_with_duplicate_username_returns_409(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    username = _unique_username("dup")
    body = {"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "viewer"}
    first = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert first.status_code == 200
    second = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert second.status_code == 409


def test_refresh_token_rotates_and_invalidates_the_old_one(client: TestClient) -> None:
    login = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    refresh_token = login.json()["data"]["refresh_token"]

    refreshed = client.post("/api/v1/refresh-token", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.text

    reused = client.post("/api/v1/refresh-token", json={"refresh_token": refresh_token})
    assert reused.status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    login = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    refresh_token = login.json()["data"]["refresh_token"]

    logout = client.post("/api/v1/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 200, logout.text

    after_logout = client.post("/api/v1/refresh-token", json={"refresh_token": refresh_token})
    assert after_logout.status_code == 401


def test_audit_log_requires_view_audit_permission(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    username = _unique_username("dev")
    client.post(
        "/api/v1/users", headers=admin_headers,
        json={"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "developer"},
    )
    login = client.post("/api/v1/login", json={"username": username, "password": "Password123!"})
    dev_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    response = client.get("/api/v1/audit", headers=dev_headers)

    assert response.status_code == 403


def test_admin_can_view_audit_log_and_it_contains_real_requests(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    client.get("/api/v1/me", headers=admin_headers)  # generates at least one more audit event

    response = client.get("/api/v1/audit", headers=admin_headers)

    assert response.status_code == 200, response.text
    events = response.json()["data"]
    assert len(events) > 0
    assert any(e["endpoint"] == "/api/v1/me" for e in events)


def test_roles_catalog_is_visible_to_any_authenticated_user(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/roles", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data.keys()) == {"admin", "analyst", "viewer", "operator", "developer", "plugin"}
    assert "manage_users" in data["admin"]
    assert "manage_users" not in data["viewer"]


def test_permissions_catalog_is_visible_to_any_authenticated_user(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/permissions", headers=headers)
    assert response.status_code == 200, response.text
    assert "manage_users" in response.json()["data"]


def test_response_includes_a_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
