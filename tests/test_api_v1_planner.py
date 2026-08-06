"""Tests for the /api/v1/planner/* endpoints, against the real app with the
real PlannerAgentService/PlanningService — no external AI (MockProvider).
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _generate_plan(user_request: str, step_id: str = "planner-s1", session_id: str = "sess-1") -> dict:
    response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {
                "step_id": step_id,
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": user_request},
            },
            "session_id": session_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_generate_plan_returns_a_completed_result_with_dynamically_discovered_agents() -> None:
    data = _generate_plan("Generate a business report.", step_id="planner-s2")

    assert data["status"] == "completed"
    planner_output = data["planner_output"]
    assert planner_output["goal"]
    steps = planner_output["execution_plan"]["steps"]
    assert len(steps) > 0
    # Agents referenced come from the live orchestration graph, never a hardcoded list.
    assert all(
        step["node_name"] in {"file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"}
        for step in steps
    )
    # Every step's description explains why that agent was selected.
    assert all(step["description"] for step in steps)


def test_generate_plan_missing_user_request_returns_422() -> None:
    response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {"step_id": "planner-bad", "name": "Bad", "node_name": "planner", "inputs": {}},
            "session_id": "sess-1",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidPlannerAgentInputError"


def test_get_plan_execution_fetches_a_previously_run_step() -> None:
    _generate_plan("Analyze uploaded sales file.", step_id="planner-s3")

    response = client.get("/api/v1/planner/plan/planner-s3")

    assert response.status_code == 200
    assert response.json()["data"]["step_id"] == "planner-s3"


def test_get_plan_execution_unknown_step_id_returns_404() -> None:
    response = client.get("/api/v1/planner/plan/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "AgentExecutionNotFoundError"


def test_preview_plan_returns_mermaid_json_and_timeline() -> None:
    data = _generate_plan("Please clean my uploaded customer records dataset.", step_id="planner-s4")
    plan = data["planner_output"]["execution_plan"]

    response = client.post("/api/v1/planner/preview", json={"plan": plan})

    assert response.status_code == 200, response.text
    preview = response.json()["data"]
    assert "flowchart" in preview["mermaid"].lower() or "graph" in preview["mermaid"].lower()
    assert plan["plan_id"] in preview["json_export"]
    assert preview["timeline"]["plan_id"] == plan["plan_id"]
    assert len(preview["timeline"]["entries"]) == len(plan["steps"])


def test_validate_plan_advances_a_sound_plan_to_validated() -> None:
    data = _generate_plan("Analyze customer table from SQL.", step_id="planner-s5")
    plan = data["planner_output"]["execution_plan"]

    response = client.post("/api/v1/planner/validate", json={"plan": plan})

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["validation"]["is_valid"] is True
    assert body["plan"]["status"] == "validated"


def test_validate_plan_flags_an_unregistered_node() -> None:
    data = _generate_plan("Analyze uploaded sales file.", step_id="planner-s6")
    plan = data["planner_output"]["execution_plan"]
    plan["steps"][0]["node_name"] = "not_a_real_agent"

    response = client.post("/api/v1/planner/validate", json={"plan": plan})

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["validation"]["is_valid"] is False
    assert any(issue["code"] == "unknown_node_name" for issue in body["validation"]["issues"])


def test_explain_plan_returns_the_why_for_every_step() -> None:
    data = _generate_plan("Generate report with recent market context.", step_id="planner-s7")
    plan = data["planner_output"]["execution_plan"]

    response = client.post("/api/v1/planner/explain", json={"plan": plan})

    assert response.status_code == 200, response.text
    explanation = response.json()["data"]
    assert explanation["goal"] == plan["goal"]
    assert len(explanation["steps"]) == len(plan["steps"])
    for step, explained in zip(plan["steps"], explanation["steps"], strict=False):
        assert explained["node_name"] == step["node_name"]
        assert explained["reasoning"] == step["description"]


def test_execute_plan_runs_it_via_planning_service() -> None:
    data = _generate_plan("Give me business recommendations from the report.", step_id="planner-s8")
    plan = data["planner_output"]["execution_plan"]

    response = client.post("/api/v1/planner/execute", json={"plan": plan})

    assert response.status_code == 200, response.text
    executed_plan = response.json()["data"]
    assert executed_plan["status"] in {"completed", "failed"}


def test_execute_plan_with_an_invalid_plan_returns_422() -> None:
    data = _generate_plan("Analyze uploaded sales file.", step_id="planner-s9")
    plan = data["planner_output"]["execution_plan"]
    plan["steps"][0]["node_name"] = "not_a_real_agent"

    response = client.post("/api/v1/planner/execute", json={"plan": plan})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "PlanValidationFailedError"
