"""Tests for the /api/v1/distributed/* endpoints against the real app —
mirrors every other REST test file's own "exercise the real thing" pattern.
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


def _register(client: TestClient, headers: dict[str, str], worker_id: str, capabilities: list[str]) -> dict:
    response = client.post(
        "/api/v1/distributed/workers/register", headers=headers,
        json={"worker_id": worker_id, "hostname": f"host-{worker_id}", "capabilities": capabilities, "maximum_parallel_tasks": 2},
    )
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def test_distributed_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/distributed/workers").status_code == 401
    assert client.post("/api/v1/distributed/workers/register", json={}).status_code == 401
    assert client.get("/api/v1/distributed/cluster").status_code == 401
    assert client.get("/api/v1/distributed/queue").status_code == 401


def test_register_worker_returns_online_worker(client: TestClient) -> None:
    headers = _admin_headers(client)
    worker = _register(client, headers, "w1", ["browser_agent"])
    assert worker["status"] == "online"
    assert worker["capabilities"] == [{"node_name": "browser_agent"}]


def test_register_filters_unrecognized_capability(client: TestClient) -> None:
    headers = _admin_headers(client)
    worker = _register(client, headers, "w2", ["browser_agent", "not_a_real_agent"])
    assert [c["node_name"] for c in worker["capabilities"]] == ["browser_agent"]


def test_list_workers_includes_a_newly_registered_one(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "w3", ["sql_agent"])
    response = client.get("/api/v1/distributed/workers", headers=headers)
    assert response.status_code == 200
    assert "w3" in [w["worker_id"] for w in response.json()["data"]]


def test_heartbeat_endpoint_refreshes_and_revives(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "w4", ["sql_agent"])
    response = client.post(
        "/api/v1/distributed/workers/heartbeat", headers=headers, json={"worker_id": "w4", "active_task_count": 0},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "online"


def test_drain_then_shutdown_a_worker(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "w5", ["sql_agent"])

    drained = client.post("/api/v1/distributed/workers/drain", headers=headers, json={"worker_id": "w5"})
    assert drained.json()["data"]["status"] == "draining"

    shut_down = client.post("/api/v1/distributed/workers/shutdown", headers=headers, json={"worker_id": "w5"})
    assert shut_down.json()["data"]["status"] == "offline"


def test_worker_action_on_unknown_worker_returns_404(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.post("/api/v1/distributed/workers/drain", headers=headers, json={"worker_id": "does-not-exist"})
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "WorkerNotFoundError"


def test_cluster_statistics_reflects_registered_workers(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "w6", ["browser_agent"])
    response = client.get("/api/v1/distributed/cluster", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["total_workers"] >= 1


def test_queue_snapshot_has_active_and_retry_lists(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/distributed/queue", headers=headers)
    assert response.status_code == 200
    assert set(response.json()["data"].keys()) == {"active", "retry"}
