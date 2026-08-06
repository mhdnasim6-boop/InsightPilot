"""Tests for the /api/v1/realtime/* endpoints against the real app — mirrors
every other REST test file's own "exercise the real thing" pattern.
"""

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


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/realtime/events").status_code == 401
    assert client.get("/api/v1/realtime/subscriptions").status_code == 401
    assert client.get("/api/v1/realtime/replay").status_code == 401


def test_list_event_types_returns_all_24(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/realtime/events", headers=headers)
    assert response.status_code == 200, response.text
    assert len(response.json()["data"]) == 24
    assert "workflow_started" in response.json()["data"]


def test_list_subscriptions_returns_a_list(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/realtime/subscriptions", headers=headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json()["data"], list)


def test_replay_returns_the_login_events_it_just_caused(client: TestClient) -> None:
    headers = _admin_headers(client)  # publishes a real UserLoggedIn
    response = client.get("/api/v1/realtime/replay", params={"count": 10}, headers=headers)
    assert response.status_code == 200, response.text
    event_types = [e["event"]["event_type"] for e in response.json()["data"]]
    assert "user_logged_in" in event_types


def test_replay_rejects_both_count_and_since(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get(
        "/api/v1/realtime/replay", params={"count": 10, "since": "2026-01-01T00:00:00Z"}, headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidReplayRequestError"


def test_replay_filters_by_event_type(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get(
        "/api/v1/realtime/replay", params={"count": 50, "event_type": ["plugin_loaded"]}, headers=headers,
    )
    assert response.status_code == 200, response.text
    event_types = {e["event"]["event_type"] for e in response.json()["data"]}
    assert event_types <= {"plugin_loaded"}


def test_replay_with_no_matching_events_returns_an_empty_list(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get(
        "/api/v1/realtime/replay", params={"count": 50, "workflow_id": "does-not-exist"}, headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == []
