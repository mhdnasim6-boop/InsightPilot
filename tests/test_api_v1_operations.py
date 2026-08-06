"""Tests for the /api/v1/operations/* endpoints against the real app,
with real startup genuinely having run via lifespan — mirrors every
other REST test file's own "exercise the real thing" pattern.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_alive(client: TestClient) -> None:
    response = client.get("/api/v1/operations/health")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["alive"] is True
    assert data["application"] == "InsightPilot"


def test_readiness_reports_ready_after_real_startup(client: TestClient) -> None:
    response = client.get("/api/v1/operations/readiness")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["ready"] is True
    stage_names = [stage["name"] for stage in data["stages"]]
    assert stage_names == [
        "configuration", "plugin_loading", "registries", "memory", "observability", "execution", "api_ready",
    ]
    assert all(stage["status"] == "completed" for stage in data["stages"])


def test_diagnostics_reflects_real_registered_state(client: TestClient) -> None:
    response = client.get("/api/v1/operations/diagnostics")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # The real demo plugin (backend/extensions/csv_statistics_plugin/) auto-loads at startup.
    assert "csv_statistics_plugin" in data["dependency_report"]["loaded_plugins"]
    assert "csv_row_count" in data["dependency_report"]["registered_tools"]
    assert data["dependency_report"]["registered_agents"]  # the real orchestration graph's node names
    assert len(data["feature_flags"]) == 6


def test_configuration_returns_the_active_profile_and_validation(client: TestClient) -> None:
    response = client.get("/api/v1/operations/configuration")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["profile"] == "development"
    assert "validation" in data
    assert isinstance(data["validation"]["is_valid"], bool)


def test_feature_flags_returns_every_flag(client: TestClient) -> None:
    response = client.get("/api/v1/operations/feature-flags")
    assert response.status_code == 200, response.text
    flags = response.json()["data"]
    names = {flag["name"] for flag in flags}
    assert names == {
        "memory_enabled", "plugins_enabled", "reflection_enabled",
        "adaptive_planning_enabled", "browser_agent_enabled", "mcp_enabled",
    }
    assert all(flag["enabled"] for flag in flags)
