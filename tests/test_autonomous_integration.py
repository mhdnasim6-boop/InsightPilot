"""Integration tests: prove the autonomous optimization layer genuinely composes with
the real platform stack — WorkflowService, DistributedExecutionService,
FederationService, ObservabilityService/MetricsService, MemoryService, and
RealtimeService — end-to-end, against the real app, real DI wiring, and real agents,
never a hand-built fixture. Mirrors ``tests/test_federation_integration.py``'s own
pattern.
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


def _execute_a_real_workflow(client: TestClient, headers: dict[str, str]) -> dict:
    body = {
        "name": "Autonomous integration workflow", "description": "x",
        "steps": [
            {
                "step_id": "s1", "name": "Search", "node_name": "browser_agent",
                "inputs": {"search_request": "InsightPilot autonomous optimization"},
            }
        ],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    assert created.status_code == 200, created.text
    workflow_id = created.json()["data"]["workflow_id"]
    executed = client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": "auto-sess"}, headers=headers)
    assert executed.status_code == 200, executed.text
    return dict(executed.json()["data"])


# -- WorkflowService / ObservabilityService / MetricsService ------------------------------


def test_performance_profile_reflects_a_real_workflow_execution(client: TestClient) -> None:
    headers = _admin_headers(client)
    execution = _execute_a_real_workflow(client, headers)
    assert execution["status"] == "completed"

    report = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]
    profile = report["performance_profile"]
    assert profile["workflow_statistics"]["total_executions"] >= 1
    assert profile["execution_metrics"]["trace_count"] >= 1


# -- DistributedExecutionService / FederationService ---------------------------------------


def test_performance_profile_reflects_a_real_registered_worker(client: TestClient) -> None:
    headers = _admin_headers(client)
    registered = client.post(
        "/api/v1/distributed/workers/register", headers=headers,
        json={"worker_id": "autonomous-integration-worker", "hostname": "h1", "capabilities": ["browser_agent"]},
    )
    assert registered.status_code == 200, registered.text

    report = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]
    profile = report["performance_profile"]
    assert profile["worker_fleet_statistics"]["total_workers"] >= 1
    assert profile["federation_statistics"]["total_clusters"] >= 1


# -- MemoryService --------------------------------------------------------------------------


def test_performance_profile_reflects_a_real_stored_memory(client: TestClient) -> None:
    headers = _admin_headers(client)
    remembered = client.post(
        "/api/v1/memory", headers=headers,
        json={"title": "Autonomous integration memory", "summary": "x", "memory_type": "decision", "importance": 0.9},
    )
    assert remembered.status_code == 200, remembered.text

    report = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]
    assert report["performance_profile"]["memory_statistics"]["total_items"] >= 1


# -- RealtimeService: analyzing does not disturb the real event stream ----------------------


def test_realtime_events_still_fire_normally_around_an_autonomous_analysis(client: TestClient) -> None:
    headers = _admin_headers(client)
    client.post("/api/v1/autonomous/analyze", headers=headers)
    execution = _execute_a_real_workflow(client, headers)
    client.post("/api/v1/autonomous/analyze", headers=headers)

    replay = client.get(
        "/api/v1/realtime/replay", params={"workflow_id": execution["workflow_id"], "count": 200}, headers=headers,
    )
    event_types = [e["event"]["event_type"] for e in replay.json()["data"]]
    assert "workflow_started" in event_types
    assert "workflow_completed" in event_types


# -- Zero-data path: a fresh analysis pass never errors and stays advisory-only -------------


def test_analysis_report_is_fully_advisory_even_once_real_platform_data_exists(client: TestClient) -> None:
    headers = _admin_headers(client)
    _execute_a_real_workflow(client, headers)
    report = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]
    for action in report["actions"]:
        assert action["safe_to_automate"] is False
    for recommendation in report["recommendations"]:
        assert recommendation["requires_human_approval"] is True
