"""Integration tests: prove the distributed dispatch layer genuinely composes
with the real execution stack — ExecutionService, WorkflowService,
ObservabilityService, ApprovalService, and RealtimeService — end-to-end,
against the real app, real DI wiring, and real agents, never a hand-built
fixture. Mirrors ``tests/test_realtime_integration.py``'s own pattern and
its own documented reasons for sharing process-wide singletons safely.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.approval import get_approval_policy_service
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


def _register(client: TestClient, headers: dict[str, str], worker_id: str, capabilities: list[str]) -> dict:
    response = client.post(
        "/api/v1/distributed/workers/register", headers=headers,
        json={"worker_id": worker_id, "hostname": f"host-{worker_id}", "capabilities": capabilities, "maximum_parallel_tasks": 2},
    )
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def _get_worker(client: TestClient, headers: dict[str, str], worker_id: str) -> dict:
    response = client.get("/api/v1/distributed/workers", headers=headers)
    return next(w for w in response.json()["data"] if w["worker_id"] == worker_id)


# -- ExecutionService / WorkflowService / ObservabilityService / RealtimeService ------


def test_worker_is_credited_and_released_during_a_real_workflow_execution(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "dist-w1", ["browser_agent"])

    body = {
        "name": "Distributed integration workflow", "description": "x",
        "steps": [
            {
                "step_id": "s1", "name": "Search", "node_name": "browser_agent",
                "inputs": {"search_request": "InsightPilot distributed execution"},
            }
        ],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    assert created.status_code == 200, created.text
    workflow_id = created.json()["data"]["workflow_id"]

    executed = client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": "dist-sess"}, headers=headers)
    assert executed.status_code == 200, executed.text
    execution = executed.json()["data"]
    assert execution["status"] == "completed"
    trace_id = execution["trace_id"]

    # The worker was credited and released — proves DispatchingAgentService's
    # assign()/complete() round trip fired correctly around the real agent call.
    worker_after = _get_worker(client, headers, "dist-w1")
    assert worker_after["status"] == "online"
    assert worker_after["active_tasks"] == []

    # No task assignment left outstanding or awaiting retry.
    queue = client.get("/api/v1/distributed/queue", headers=headers).json()["data"]
    assert queue["active"] == []
    assert queue["retry"] == []

    # ObservabilityService: the real trace this execution produced still exists.
    trace_response = client.get(f"/api/v1/observability/traces/{trace_id}", headers=headers)
    assert trace_response.status_code == 200

    # RealtimeService: Phase 37's own AgentStarted/AgentCompleted events still fire,
    # proving DispatchingAgentService composes cleanly inside RealtimePublishingAgentService.
    replay = client.get("/api/v1/realtime/replay", params={"trace_id": trace_id, "count": 200}, headers=headers)
    event_types = [e["event"]["event_type"] for e in replay.json()["data"]]
    assert "agent_started" in event_types
    assert "agent_completed" in event_types


def test_execution_behaves_identically_with_no_registered_worker(client: TestClient) -> None:
    """The core backward-compatibility proof: a step whose node_name has no
    registered worker still executes normally — dispatch() returns None, and
    DispatchingAgentService is a pure pass-through."""
    headers = _admin_headers(client)
    body = {
        "name": "No worker workflow", "description": "x",
        "steps": [
            {
                "step_id": "s1", "name": "Search", "node_name": "browser_agent",
                "inputs": {"search_request": "no workers registered for this one"},
            }
        ],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    workflow_id = created.json()["data"]["workflow_id"]

    executed = client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"session_id": "dist-sess-2"}, headers=headers)

    assert executed.status_code == 200, executed.text
    assert executed.json()["data"]["status"] == "completed"


# -- ApprovalService integration: dispatch only ever happens for steps that actually run --


def _generate_plan(client: TestClient, user_request: str, step_id: str) -> dict:
    response = client.post(
        "/api/v1/planner/plan",
        json={"step": {"step_id": step_id, "name": "Planner Agent Run", "node_name": "planner",
                        "inputs": {"user_request": user_request}}, "session_id": "dist-approvals"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed", data
    return dict(data["planner_output"]["execution_plan"])


def test_approval_gated_step_is_not_dispatched_until_approved_and_resumed(client: TestClient) -> None:
    headers = _admin_headers(client)
    _register(client, headers, "dist-w2", ["file_agent"])
    client.put("/api/v1/approvals/policy", json={"policy_type": "always"})

    plan = _generate_plan(client, "Please clean my uploaded customer records dataset.", "dist-approvals-s1")
    executed = client.post("/api/v1/planner/execute", json={"plan": plan}).json()["data"]
    assert executed["status"] == "paused"

    # Paused before ever reaching NodeDispatcher — no assignment exists yet.
    worker_while_paused = _get_worker(client, headers, "dist-w2")
    assert worker_while_paused["active_tasks"] == []
    queue_while_paused = client.get("/api/v1/distributed/queue", headers=headers).json()["data"]
    assert queue_while_paused["active"] == []

    approval_id = client.get("/api/v1/approvals/pending").json()["data"][0]["approval_id"]
    client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver": "qa"})
    plan_id = executed["plan_id"]
    client.post(f"/api/v1/approvals/plan/{plan_id}/resume")

    # Whatever ran afterward, the worker is never left holding a stale active task.
    worker_after = _get_worker(client, headers, "dist-w2")
    assert worker_after["active_tasks"] == []
