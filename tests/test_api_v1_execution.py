"""Tests for the /api/v1/execution/* endpoints, against the real app with
real (MockProvider-backed) agents — every execution here comes from an
actual plan generated through /api/v1/planner/plan, not a hand-built fixture.

Mirrors ``test_api_v1_observability.py``'s own pattern: ``ApprovalPolicyService``
is a process-wide DI singleton shared by the whole test suite via
``TestClient(app)``, so the ``_reset_policy`` fixture restores NEVER after
every test here.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.approval import get_approval_policy_service
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_policy() -> Iterator[None]:
    policy_service = get_approval_policy_service()
    yield
    policy_service.set_policy(policy_service.get_policy().model_copy(update={"policy_type": "never"}))


def _set_policy(policy_type: str) -> None:
    response = client.put("/api/v1/approvals/policy", json={"policy_type": policy_type})
    assert response.status_code == 200, response.text


def _generate_plan(user_request: str, step_id: str) -> dict:
    response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {
                "step_id": step_id,
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": user_request},
            },
            "session_id": "sess-execution",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed", data
    plan = dict(data["planner_output"]["execution_plan"])
    plan["status"] = "ready"
    return plan


def test_start_execution_runs_a_real_plan_to_completion() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "exec-s1")

    response = client.post("/api/v1/execution/start", json={"plan": plan, "session_id": "sess-execution"})

    assert response.status_code == 200, response.text
    state = response.json()["data"]
    assert state["plan_id"] == plan["plan_id"]
    assert state["status"] in {"completed", "failed"}
    assert len(state["steps"]) == len(plan["steps"])


def test_start_execution_with_a_non_ready_plan_returns_422() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "exec-s2")
    plan["status"] = "draft"

    response = client.post("/api/v1/execution/start", json={"plan": plan})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "PlanNotReadyError"


def test_get_execution_and_progress_and_graph() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "exec-s3")
    started = client.post("/api/v1/execution/start", json={"plan": plan}).json()["data"]
    execution_id = started["execution_id"]

    get_response = client.get(f"/api/v1/execution/{execution_id}")
    assert get_response.status_code == 200
    assert get_response.json()["data"]["execution_id"] == execution_id

    progress_response = client.get(f"/api/v1/execution/{execution_id}/progress")
    assert progress_response.status_code == 200
    progress = progress_response.json()["data"]
    assert progress["total_steps"] == len(plan["steps"])

    graph_response = client.get(f"/api/v1/execution/{execution_id}/graph")
    assert graph_response.status_code == 200
    assert "graph TD;" in graph_response.json()["data"]


def test_get_execution_unknown_id_returns_404() -> None:
    response = client.get("/api/v1/execution/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "ExecutionNotFoundError"


def test_resume_a_non_paused_execution_returns_409() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "exec-s4")
    started = client.post("/api/v1/execution/start", json={"plan": plan}).json()["data"]

    response = client.post(f"/api/v1/execution/{started['execution_id']}/resume")

    assert response.status_code == 409
    assert response.json()["errors"]["type"] == "ExecutionNotPausedError"


def test_paused_execution_can_be_approved_and_resumed_to_completion() -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "exec-s5")

    started = client.post(
        "/api/v1/execution/start", json={"plan": plan, "session_id": "sess-execution"}
    ).json()["data"]
    execution_id = started["execution_id"]
    assert started["status"] == "paused"

    resumed = started
    attempts = 0
    while resumed["status"] == "paused":
        pending = client.get("/api/v1/approvals/pending").json()["data"]
        pending_for_this_plan = [a for a in pending if a["plan_id"] == plan["plan_id"]]
        assert pending_for_this_plan, "expected a pending approval while execution is paused"
        client.post(f"/api/v1/approvals/{pending_for_this_plan[0]['approval_id']}/approve", json={"approver": "qa"})
        resumed = client.post(f"/api/v1/execution/{execution_id}/resume").json()["data"]
        attempts += 1
        assert attempts <= 10

    assert resumed["status"] == "completed"


def test_cancel_execution_settles_a_paused_plan() -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "exec-s6")
    started = client.post("/api/v1/execution/start", json={"plan": plan}).json()["data"]
    assert started["status"] == "paused"

    response = client.post(f"/api/v1/execution/{started['execution_id']}/cancel")

    assert response.status_code == 200, response.text
    cancelled = response.json()["data"]
    assert cancelled["status"] == "cancelled"


def test_cancel_execution_unknown_id_returns_404() -> None:
    response = client.post("/api/v1/execution/does-not-exist/cancel")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "ExecutionNotFoundError"
