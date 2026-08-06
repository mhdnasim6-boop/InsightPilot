"""Tests for the /api/v1/agents/browser/* endpoints, against the real app with the
real (deterministic, mock-backed) BrowserService. Mirrors test_api_v1_sql_agent.py.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _step(step_id: str, **inputs: object) -> dict:
    return {
        "step_id": step_id,
        "name": "Browser Agent Run",
        "node_name": "browser_agent",
        "inputs": inputs,
    }


def test_execute_returns_a_completed_result() -> None:
    response = client.post(
        "/api/v1/agents/browser/execute",
        json={
            "step": _step("api-browser-s1", search_request="Acme Corp"),
            "session_id": "sess-1",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert len(data["sources"]) == 3
    assert data["summaries"][0]["query"] == "Acme Corp"


def test_execute_with_no_search_relevant_input_returns_a_skipped_result() -> None:
    response = client.post(
        "/api/v1/agents/browser/execute",
        json={"step": _step("api-browser-s2"), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "skipped"
    assert data["sources"] == []


def test_execute_missing_session_id_returns_422() -> None:
    step = _step("api-browser-s3", search_request="Acme Corp")

    response = client.post("/api/v1/agents/browser/execute", json={"step": step})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_with_a_malformed_search_request_returns_422() -> None:
    step = _step("api-browser-s4", search_request=123)

    response = client.post(
        "/api/v1/agents/browser/execute", json={"step": step, "session_id": "sess-1"}
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_get_execution_fetches_a_previously_run_step() -> None:
    client.post(
        "/api/v1/agents/browser/execute",
        json={
            "step": _step("api-browser-s5", search_request="Acme Corp"),
            "session_id": "sess-1",
        },
    )

    response = client.get("/api/v1/agents/browser/executions/api-browser-s5")

    assert response.status_code == 200
    assert response.json()["data"]["step_id"] == "api-browser-s5"


def test_get_execution_unknown_step_id_returns_404() -> None:
    response = client.get("/api/v1/agents/browser/executions/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "AgentExecutionNotFoundError"


def test_browser_agent_execution_is_not_visible_through_the_file_agent_list_endpoint() -> (
    None
):
    """Proves BrowserAgent has its own, separate result store — unlike SQLAgent,
    which deliberately shares FileAgent's store (see backend/api/v1/sql_agent.py)."""
    client.post(
        "/api/v1/agents/browser/execute",
        json={
            "step": _step("api-browser-s6", search_request="Acme Corp"),
            "session_id": "sess-1",
        },
    )

    response = client.get("/api/v1/agents/file/executions")

    assert response.status_code == 200
    step_ids = {item["step_id"] for item in response.json()["data"]}
    assert "api-browser-s6" not in step_ids
