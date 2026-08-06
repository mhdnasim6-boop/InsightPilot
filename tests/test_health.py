"""Tests for the /api/v1/health endpoint and the unified response envelope."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_check() -> None:
    """Health endpoint should report healthy status wrapped in the success envelope."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert body["data"]["application"] == "InsightPilot"
    assert body["data"]["version"] == "0.1.0"


def test_not_found_uses_unified_error_envelope() -> None:
    """An unknown route should return the unified failure envelope, not a bare 404."""
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["errors"]["status_code"] == 404
