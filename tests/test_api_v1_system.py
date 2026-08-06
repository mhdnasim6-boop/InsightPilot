"""Tests for the /api/v1/system endpoint."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_system_status_aggregates_all_sections() -> None:
    """System status should aggregate health, AI provider, model info, and graph metadata."""
    response = client.get("/api/v1/system")

    assert response.status_code == 200
    status = response.json()["data"]
    assert status["health"]["status"] == "healthy"
    assert status["ai_provider"]
    assert status["model_info"]["provider"]
    assert len(status["graph_metadata"]["nodes"]) > 0
    assert status["application_version"]
