"""Integration tests: prove the federation layer genuinely composes with the
real execution stack — DistributedExecutionService, WorkflowService,
ObservabilityService, RealtimeService, and ApprovalService — end-to-end,
against the real app, real DI wiring, and real agents, never a hand-built
fixture. Mirrors ``tests/test_distributed_integration.py``'s own pattern.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.approval import get_approval_policy_service
from backend.federation.services.federation_service import LOCAL_CLUSTER_ID
from backend.main import app

_ADMIN_USERNAME = "admin"
_ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_policy() -> Iterator[None]:
    policy_service = get_approval_policy_service()
    yield
    policy_service.set_policy(policy_service.get_policy().model_copy(update={"policy_type": "never"}))


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _routing_decisions_for(client: TestClient, headers: dict[str, str], workflow_id: str) -> list[dict]:
    response = client.get("/api/v1/federation/routing", headers=headers)
    return [d for d in response.json()["data"] if d["workflow_id"] == workflow_id]


# -- WorkflowService / DistributedExecutionService -------------------------------------


def test_workflow_execution_is_routed_to_local_cluster_and_completes(client: TestClient) -> None:
    headers = _admin_headers(client)
    body = {
        "name": "Federation integration workflow", "description": "x",
        "steps": [
            {
                "step_id": "s1", "name": "Search", "node_name": "browser_agent",
                "inputs": {"search_request": "InsightPilot federated orchestration"},
            }
        ],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    assert created.status_code == 200, created.text
    workflow_id = created.json()["data"]["workflow_id"]

    executed = client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": "fed-sess"}, headers=headers)
    assert executed.status_code == 200, executed.text
    execution = executed.json()["data"]
    assert execution["status"] == "completed"
    trace_id = execution["trace_id"]

    decisions = _routing_decisions_for(client, headers, workflow_id)
    assert len(decisions) == 1
    assert decisions[0]["selected_cluster_id"] == LOCAL_CLUSTER_ID
    assert decisions[0]["status"] == "completed"
    assert decisions[0]["required_agents"] == ["browser_agent"]

    # The local cluster is never left holding a stale credit — proves
    # DistributedExecutionService's own real dispatch (Phase 38) and federation's
    # own routing credit both released cleanly around the same real execution.
    local_cluster = next(c for c in client.get("/api/v1/federation/clusters", headers=headers).json()["data"] if c["is_local"])
    assert local_cluster["active_remote_executions"] == []

    # ObservabilityService: the real trace this execution produced still exists.
    trace_response = client.get(f"/api/v1/observability/traces/{trace_id}", headers=headers)
    assert trace_response.status_code == 200

    # RealtimeService: Phase 37's own WorkflowStarted/WorkflowCompleted events still
    # fire — proving FederationCoordinator composes cleanly around RealtimePublishingWorkflowService.
    replay = client.get("/api/v1/realtime/replay", params={"workflow_id": workflow_id, "count": 200}, headers=headers)
    event_types = [e["event"]["event_type"] for e in replay.json()["data"]]
    assert "workflow_started" in event_types
    assert "workflow_completed" in event_types


def test_workflow_execution_with_no_matching_worker_still_routes_and_completes(client: TestClient) -> None:
    """The local cluster's own capabilities are derived live from AgentCapabilityRegistry
    (every real agent), so this always succeeds regardless of Phase 38 worker registration —
    proving federation routing never depends on distributed workers being registered."""
    headers = _admin_headers(client)
    body = {
        "name": "Federation no-worker workflow", "description": "x",
        "steps": [{"step_id": "s1", "name": "Search", "node_name": "browser_agent", "inputs": {"search_request": "x"}}],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    workflow_id = created.json()["data"]["workflow_id"]

    executed = client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": "s"}, headers=headers)

    assert executed.status_code == 200, executed.text
    assert executed.json()["data"]["status"] == "completed"


# -- ApprovalService integration: routing is not disturbed by an approval-gated pause --


def test_approval_gated_workflow_still_routes_before_pausing(client: TestClient) -> None:
    headers = _admin_headers(client)
    client.put("/api/v1/approvals/policy", json={"policy_type": "always"})
    body = {
        "name": "Federation approval-gated workflow", "description": "x",
        "steps": [
            {
                "step_id": "s1", "name": "Search", "node_name": "browser_agent",
                "inputs": {"search_request": "federated approval test"},
            }
        ],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    workflow_id = created.json()["data"]["workflow_id"]

    executed = client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": "s"}, headers=headers)
    assert executed.status_code == 200, executed.text
    assert executed.json()["data"]["status"] == "paused"

    # A routing decision was still made and dispatched (the local execute() call
    # returned successfully, just with a paused workflow inside it) — see
    # FederationCoordinator's own docstring for why this closes out as "completed."
    decisions = _routing_decisions_for(client, headers, workflow_id)
    assert len(decisions) == 1
    assert decisions[0]["status"] == "completed"

    # Resuming does not create a second routing decision — resume() is never
    # wrapped: "already-running work remains owned by its original cluster."
    workflow_execution_id = executed.json()["data"]["workflow_execution_id"]
    client.post(f"/api/v1/workflows/{workflow_id}/resume", json={"session_id": "s"}, headers=headers)
    assert len(_routing_decisions_for(client, headers, workflow_id)) == 1
    assert workflow_execution_id  # sanity: the paused execution really had an id
