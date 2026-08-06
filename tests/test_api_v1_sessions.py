"""Tests for the /api/v1/sessions endpoints."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_create_session() -> None:
    """Creating a session should return a session_id and empty uploaded_files."""
    response = client.post("/api/v1/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["session_id"]
    assert body["data"]["uploaded_files"] == []


def test_get_session() -> None:
    """Fetching a previously created session should return the same session_id."""
    created = client.post("/api/v1/sessions").json()["data"]

    response = client.get(f"/api/v1/sessions/{created['session_id']}")

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == created["session_id"]


def test_get_missing_session_returns_404() -> None:
    """Fetching an unknown session_id should use the unified error envelope."""
    response = client.get("/api/v1/sessions/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["errors"]["status_code"] == 404
