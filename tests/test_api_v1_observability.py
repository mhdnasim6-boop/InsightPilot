"""Tests for the /api/v1/observability/* endpoints, against the real app with
real (MockProvider-backed) agents — every trace here comes from an actual
plan run through /api/v1/planner/execute, not a hand-built fixture.

Mirrors ``test_api_v1_approvals.py``'s own pattern: ``ApprovalPolicyService``
is a process-wide DI singleton shared by the whole test suite via
``TestClient(app)``, so the ``_reset_policy`` fixture restores NEVER after
every test here. Assertions against globally-aggregated endpoints
(``/observability/traces``, ``/observability/metrics/*``) use ``>=``/
"contains" checks rather than exact counts, since other test files running
in the same session add their own traces to the same shared store.
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
            "session_id": "sess-observability",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed", data
    return dict(data["planner_output"]["execution_plan"])


def _execute_plan(plan: dict) -> dict:
    response = client.post("/api/v1/planner/execute", json={"plan": plan})
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def test_completed_plan_produces_a_finalized_trace_reachable_by_plan_and_trace_id() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "obs-s1")
    executed = _execute_plan(plan)
    plan_id = executed["plan_id"]
    assert executed["status"] == "completed"

    by_plan = client.get(f"/api/v1/observability/traces/plan/{plan_id}")
    assert by_plan.status_code == 200, by_plan.text
    trace = by_plan.json()["data"]
    assert trace["plan_id"] == plan_id
    assert trace["status"] == "completed"
    assert trace["end_time"] is not None
    assert trace["duration_ms"] is not None
    assert len(trace["agent_traces"]) >= 1

    by_id = client.get(f"/api/v1/observability/traces/{trace['trace_id']}")
    assert by_id.status_code == 200, by_id.text
    assert by_id.json()["data"]["trace_id"] == trace["trace_id"]


def test_list_traces_includes_a_just_finalized_trace() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "obs-s2")
    executed = _execute_plan(plan)
    trace = client.get(f"/api/v1/observability/traces/plan/{executed['plan_id']}").json()["data"]

    response = client.get("/api/v1/observability/traces")

    assert response.status_code == 200
    trace_ids = {t["trace_id"] for t in response.json()["data"]}
    assert trace["trace_id"] in trace_ids


def test_trace_timeline_includes_an_agent_entry() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "obs-s3")
    executed = _execute_plan(plan)
    trace = client.get(f"/api/v1/observability/traces/plan/{executed['plan_id']}").json()["data"]

    response = client.get(f"/api/v1/observability/traces/{trace['trace_id']}/timeline")

    assert response.status_code == 200, response.text
    timeline = response.json()["data"]
    assert any(entry["kind"] == "agent" for entry in timeline)
    timestamps = [entry["start_time"] for entry in timeline]
    assert timestamps == sorted(timestamps)


@pytest.mark.parametrize(
    ("export_format", "expected_snippet"),
    [("json", '"trace_id"'), ("markdown", "# Execution Trace"), ("csv", "kind,name,start_time")],
)
def test_export_trace_supports_every_format(export_format: str, expected_snippet: str) -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", f"obs-s4-{export_format}")
    executed = _execute_plan(plan)
    trace = client.get(f"/api/v1/observability/traces/plan/{executed['plan_id']}").json()["data"]

    response = client.get(
        f"/api/v1/observability/traces/{trace['trace_id']}/export", params={"format": export_format}
    )

    assert response.status_code == 200, response.text
    content = response.json()["data"]
    assert isinstance(content, str)
    assert expected_snippet in content


def test_agent_metrics_reflect_a_completed_run() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "obs-s5")
    _execute_plan(plan)

    response = client.get("/api/v1/observability/metrics/agents")

    assert response.status_code == 200
    agent_names = {m["agent_name"] for m in response.json()["data"]}
    assert "file_agent" in agent_names


def test_metrics_summary_reports_at_least_one_trace() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "obs-s6")
    _execute_plan(plan)

    response = client.get("/api/v1/observability/metrics/summary")

    assert response.status_code == 200
    summary = response.json()["data"]
    assert summary["trace_count"] >= 1


def test_paused_plan_produces_a_live_trace_with_a_pending_approval() -> None:
    _set_policy("always")
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "obs-s7")

    executed = _execute_plan(plan)
    assert executed["status"] == "paused"

    trace = client.get(f"/api/v1/observability/traces/plan/{executed['plan_id']}").json()["data"]

    assert trace["status"] == "paused"
    assert trace["end_time"] is None
    assert len(trace["approval_traces"]) >= 1
    assert trace["approval_traces"][0]["status"] == "pending"


def test_get_trace_for_unknown_id_returns_404() -> None:
    response = client.get("/api/v1/observability/traces/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "TraceNotFoundError"


def test_get_trace_for_unknown_plan_returns_404() -> None:
    response = client.get("/api/v1/observability/traces/plan/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "TraceNotFoundError"
