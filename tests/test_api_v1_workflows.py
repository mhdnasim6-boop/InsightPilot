"""Tests for the /api/v1/workflows/* endpoints against the real app, with
the real default orchestration graph (file_agent, sql_agent, browser_agent,
report_agent, executive_summary_agent) and the real seeded admin account —
mirrors every other REST test file's own "exercise the real thing" pattern.
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


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _create_workflow(client: TestClient, headers: dict[str, str], name: str | None = None) -> dict:
    body = {
        "name": name or f"Workflow {uuid.uuid4().hex[:8]}",
        "description": "A real-agent smoke-test workflow.",
        "steps": [{"step_id": "s1", "name": "Search", "node_name": "browser_agent", "kind": "agent", "inputs": {}}],
    }
    response = client.post("/api/v1/workflows", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_workflows_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/workflows").status_code == 401
    assert client.post("/api/v1/workflows", json={}).status_code == 401


def test_create_workflow_requires_objective_or_name_and_steps(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.post("/api/v1/workflows", json={}, headers=headers)
    assert response.status_code == 422


def test_create_and_get_workflow(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)

    response = client.get(f"/api/v1/workflows/{created['workflow_id']}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["definition"]["name"] == created["definition"]["name"]


def test_get_unknown_workflow_returns_404(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/workflows/does-not-exist", headers=headers)
    assert response.status_code == 404


def test_list_workflows_includes_a_newly_created_one(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)

    response = client.get("/api/v1/workflows", headers=headers)

    assert response.status_code == 200, response.text
    ids = [w["workflow_id"] for w in response.json()["data"]]
    assert created["workflow_id"] in ids


def test_execute_workflow_runs_it_to_completion(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)

    response = client.post(
        f"/api/v1/workflows/{created['workflow_id']}/execute", json={"session_id": "sess-1"}, headers=headers,
    )

    assert response.status_code == 200, response.text
    execution = response.json()["data"]
    assert execution["status"] == "completed"
    assert execution["completed_steps"] == ["s1"]
    assert execution["optimization_id"]
    assert execution["trace_id"]
    assert execution["reflection_id"]


def test_cancel_an_already_completed_workflow_execution_is_a_no_op(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)
    client.post(f"/api/v1/workflows/{created['workflow_id']}/execute", json={"session_id": "sess-1"}, headers=headers)

    response = client.post(f"/api/v1/workflows/{created['workflow_id']}/cancel", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "completed"


def test_pause_an_already_completed_workflow_execution_is_a_no_op(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)
    client.post(f"/api/v1/workflows/{created['workflow_id']}/execute", json={"session_id": "sess-1"}, headers=headers)

    response = client.post(f"/api/v1/workflows/{created['workflow_id']}/pause", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "completed"


def test_resume_without_a_prior_execution_returns_404(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)

    response = client.post(f"/api/v1/workflows/{created['workflow_id']}/resume", json={}, headers=headers)

    assert response.status_code == 404


def test_clone_workflow_creates_a_new_draft(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)

    response = client.post(f"/api/v1/workflows/{created['workflow_id']}/clone", json={}, headers=headers)

    assert response.status_code == 200, response.text
    cloned = response.json()["data"]
    assert cloned["workflow_id"] != created["workflow_id"]
    assert cloned["cloned_from"] == created["workflow_id"]
    assert cloned["status"] == "draft"


def test_workflow_statistics_after_execution(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)
    client.post(f"/api/v1/workflows/{created['workflow_id']}/execute", json={"session_id": "sess-1"}, headers=headers)

    response = client.get(f"/api/v1/workflows/{created['workflow_id']}/statistics", headers=headers)

    assert response.status_code == 200, response.text
    stats = response.json()["data"]
    assert stats["total_executions"] == 1
    assert stats["successful_executions"] == 1


def test_workflow_graph_is_mermaid(client: TestClient) -> None:
    headers = _admin_headers(client)
    created = _create_workflow(client, headers)

    response = client.get(f"/api/v1/workflows/{created['workflow_id']}/graph", headers=headers)

    assert response.status_code == 200, response.text
    assert "graph TD;" in response.json()["data"]


def test_a_viewer_cannot_execute_a_workflow(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    username = f"viewer_{uuid.uuid4().hex[:8]}"
    client.post(
        "/api/v1/users", headers=admin_headers,
        json={"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "viewer"},
    )
    login = client.post("/api/v1/login", json={"username": username, "password": "Password123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    created = _create_workflow(client, admin_headers)

    response = client.post(
        f"/api/v1/workflows/{created['workflow_id']}/execute", json={}, headers=viewer_headers,
    )

    assert response.status_code == 403


def test_a_viewer_can_list_and_view_workflows(client: TestClient) -> None:
    admin_headers = _admin_headers(client)
    username = f"viewer2_{uuid.uuid4().hex[:8]}"
    client.post(
        "/api/v1/users", headers=admin_headers,
        json={"username": username, "email": f"{username}@example.com", "password": "Password123!", "role": "viewer"},
    )
    login = client.post("/api/v1/login", json={"username": username, "password": "Password123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    response = client.get("/api/v1/workflows", headers=viewer_headers)

    assert response.status_code == 200, response.text
