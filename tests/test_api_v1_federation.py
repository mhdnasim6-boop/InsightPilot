"""Tests for the /api/v1/federation/* endpoints against the real app —
mirrors every other REST test file's own "exercise the real thing" pattern.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.federation.services.federation_service import LOCAL_CLUSTER_ID
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


def _register(client: TestClient, headers: dict[str, str], cluster_id: str) -> dict:
    response = client.post(
        "/api/v1/federation/clusters/register", headers=headers,
        json={
            "cluster_id": cluster_id, "name": f"Cluster {cluster_id}", "endpoint": f"https://{cluster_id}.example.com",
            "capabilities": {"supported_agents": ["browser_agent"], "maximum_concurrent_executions": 3},
        },
    )
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def test_federation_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/federation/clusters").status_code == 401
    assert client.post("/api/v1/federation/clusters/register", json={}).status_code == 401
    assert client.get("/api/v1/federation/health").status_code == 401
    assert client.get("/api/v1/federation/statistics").status_code == 401
    assert client.get("/api/v1/federation/routing").status_code == 401


def test_list_clusters_always_includes_the_local_cluster(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/federation/clusters", headers=headers)
    assert response.status_code == 200
    ids = [c["cluster_id"] for c in response.json()["data"]]
    assert LOCAL_CLUSTER_ID in ids


def test_register_cluster_returns_online_cluster(client: TestClient) -> None:
    headers = _admin_headers(client)
    cluster = _register(client, headers, "rest-c1")
    assert cluster["status"] == "online"
    assert cluster["capabilities"]["supported_agents"] == ["browser_agent"]


def test_remove_cluster_then_it_disappears_from_the_list(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "rest-c2")
    remove_response = client.post("/api/v1/federation/clusters/remove", headers=headers, json={"cluster_id": "rest-c2"})
    assert remove_response.status_code == 200

    ids = [c["cluster_id"] for c in client.get("/api/v1/federation/clusters", headers=headers).json()["data"]]
    assert "rest-c2" not in ids


def test_remove_local_cluster_returns_422(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.post("/api/v1/federation/clusters/remove", headers=headers, json={"cluster_id": LOCAL_CLUSTER_ID})
    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "CannotRemoveLocalClusterError"


def test_remove_unknown_cluster_returns_404(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.post("/api/v1/federation/clusters/remove", headers=headers, json={"cluster_id": "does-not-exist"})
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "ClusterNotFoundError"


def test_get_health_returns_every_cluster(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "rest-c3")
    response = client.get("/api/v1/federation/health", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 2


def test_get_statistics_reflects_registered_clusters(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "rest-c4")
    response = client.get("/api/v1/federation/statistics", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["total_clusters"] >= 2


def test_get_routing_decisions_returns_a_list(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/federation/routing", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)
