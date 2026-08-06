"""Tests for the /api/v1/approvals/* endpoints and the HITL-aware
/api/v1/planner/execute, against the real app with real (MockProvider-backed)
agents and a real LangGraph checkpointer.

``ApprovalPolicyService`` is a process-wide DI singleton shared by every
test in the whole suite via ``TestClient(app)`` — the ``_reset_policy``
fixture restores NEVER (this app's own default) after every test here so
no other test file ever observes a pause it didn't ask for.
"""

from collections.abc import Iterator
from pathlib import Path

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
            "session_id": "sess-approvals",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed", data
    return dict(data["planner_output"]["execution_plan"])


def test_get_policy_defaults_to_never() -> None:
    response = client.get("/api/v1/approvals/policy")
    assert response.status_code == 200
    assert response.json()["data"]["policy_type"] == "never"


def test_set_policy_updates_the_active_policy() -> None:
    _set_policy("always")
    response = client.get("/api/v1/approvals/policy")
    assert response.json()["data"]["policy_type"] == "always"


def test_never_policy_plan_execute_completes_without_pausing() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "approvals-s1")

    response = client.post("/api/v1/planner/execute", json={"plan": plan})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "completed"


def test_always_policy_plan_execute_pauses_and_lists_a_pending_approval(tmp_path: Path) -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "approvals-s2")

    response = client.post("/api/v1/planner/execute", json={"plan": plan})

    assert response.status_code == 200, response.text
    executed = response.json()["data"]
    assert executed["status"] == "paused"
    plan_id = executed["plan_id"]

    pending_response = client.get("/api/v1/approvals/pending")
    pending_for_plan = [a for a in pending_response.json()["data"] if a["plan_id"] == plan_id]
    assert len(pending_for_plan) == 1
    assert pending_for_plan[0]["metadata"]["node_name"] == "file_agent"

    plan_approvals = client.get(f"/api/v1/approvals/plan/{plan_id}")
    assert len(plan_approvals.json()["data"]) == 1


def test_approve_then_resume_advances_a_paused_plan() -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "approvals-s3")

    executed = client.post("/api/v1/planner/execute", json={"plan": plan}).json()["data"]
    plan_id = executed["plan_id"]
    assert executed["status"] == "paused"

    approval_id = client.get("/api/v1/approvals/pending").json()["data"][0]["approval_id"]
    approve_response = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver": "qa"})
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "approved"

    resumed = client.post(f"/api/v1/approvals/plan/{plan_id}/resume").json()["data"]

    # ALWAYS gates every real agent - the single-step plan's own graph run
    # still passes through all five, so it may pause again at the next
    # one; approve-and-resume until it genuinely completes.
    attempts = 0
    while resumed["status"] == "paused":
        pending_for_plan = [a for a in client.get("/api/v1/approvals/pending").json()["data"] if a["plan_id"] == plan_id]
        assert pending_for_plan, "expected a pending approval while the plan is paused"
        client.post(f"/api/v1/approvals/{pending_for_plan[0]['approval_id']}/approve", json={"approver": "qa"})
        resumed = client.post(f"/api/v1/approvals/plan/{plan_id}/resume").json()["data"]
        attempts += 1
        assert attempts <= 10  # safety valve against an infinite loop bug

    assert resumed["status"] == "completed"

    history_response = client.get(f"/api/v1/approvals/plan/{plan_id}/history")
    event_types = [event["event_type"] for event in history_response.json()["data"]]
    assert "waiting" in event_types
    assert "approved" in event_types
    assert "resumed" in event_types
    assert "completed" in event_types


def test_approving_an_unknown_approval_returns_404() -> None:
    response = client.post("/api/v1/approvals/does-not-exist/approve", json={})
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "ApprovalNotFoundError"


def test_reject_plan_execution_fails_it_and_it_cannot_resume() -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "approvals-s4")
    executed = client.post("/api/v1/planner/execute", json={"plan": plan}).json()["data"]
    plan_id = executed["plan_id"]

    reject_response = client.post(f"/api/v1/approvals/plan/{plan_id}/reject", json={"reason": "Too risky."})
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "failed"

    resume_response = client.post(f"/api/v1/approvals/plan/{plan_id}/resume")
    assert resume_response.status_code == 409
    assert resume_response.json()["errors"]["type"] == "PlanNotPausedError"


def test_cancel_plan_execution() -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "approvals-s5")
    executed = client.post("/api/v1/planner/execute", json={"plan": plan}).json()["data"]
    plan_id = executed["plan_id"]

    cancel_response = client.post(f"/api/v1/approvals/plan/{plan_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"


def test_resuming_a_plan_with_no_paused_execution_returns_409() -> None:
    response = client.post("/api/v1/approvals/plan/never-ran/resume")
    assert response.status_code == 409
    assert response.json()["errors"]["type"] == "PlanNotPausedError"
