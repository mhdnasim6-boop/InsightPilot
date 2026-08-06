"""Tests for the /api/v1/agents/file/* endpoints, against the real app.

The TestClient runs in-process, so a file written via tmp_path is
directly readable by the backend's own IngestionService.ingest() call
— no upload/multipart step needed, since dataset_reference is a path.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

_CSV_CONTENT = "a,b\n1,2\n3,4\n5,6\n"


def _step(step_id: str, dataset_reference: str, generate_report: bool = False) -> dict:
    return {
        "step_id": step_id,
        "name": "File Agent Run",
        "node_name": "file_agent",
        "inputs": {"dataset_reference": dataset_reference, "generate_report": generate_report},
    }


def test_execute_returns_a_completed_result(tmp_path: Path) -> None:
    csv_file = tmp_path / "d.csv"
    csv_file.write_text(_CSV_CONTENT)

    response = client.post(
        "/api/v1/agents/file/execute", json={"step": _step("api-s1", str(csv_file)), "session_id": "sess-1"}
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["dataset"]["row_count"] == 3
    assert data["report"] is None


def test_execute_with_generate_report_populates_report(tmp_path: Path) -> None:
    csv_file = tmp_path / "d.csv"
    csv_file.write_text(_CSV_CONTENT)

    response = client.post(
        "/api/v1/agents/file/execute",
        json={"step": _step("api-s2", str(csv_file), generate_report=True), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["report"] is not None


def test_execute_missing_dataset_reference_returns_422() -> None:
    step = {"step_id": "api-s3", "name": "Bad", "node_name": "file_agent", "inputs": {}}

    response = client.post("/api/v1/agents/file/execute", json={"step": step, "session_id": "sess-1"})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_missing_session_id_returns_422(tmp_path: Path) -> None:
    csv_file = tmp_path / "d.csv"
    csv_file.write_text(_CSV_CONTENT)

    response = client.post("/api/v1/agents/file/execute", json={"step": _step("api-s4", str(csv_file))})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_on_a_missing_file_returns_200_with_a_failed_status() -> None:
    """A pipeline failure is a legitimate, structured result — not an HTTP error."""
    response = client.post(
        "/api/v1/agents/file/execute",
        json={"step": _step("api-s5", "/no/such/file.csv"), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["warnings"]


def test_get_execution_fetches_a_previously_run_step(tmp_path: Path) -> None:
    csv_file = tmp_path / "d.csv"
    csv_file.write_text(_CSV_CONTENT)
    client.post("/api/v1/agents/file/execute", json={"step": _step("api-s6", str(csv_file)), "session_id": "sess-1"})

    response = client.get("/api/v1/agents/file/executions/api-s6")

    assert response.status_code == 200
    assert response.json()["data"]["step_id"] == "api-s6"


def test_get_execution_unknown_step_id_returns_404() -> None:
    response = client.get("/api/v1/agents/file/executions/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "AgentExecutionNotFoundError"


def test_list_executions_includes_a_newly_run_step(tmp_path: Path) -> None:
    csv_file = tmp_path / "d.csv"
    csv_file.write_text(_CSV_CONTENT)
    client.post("/api/v1/agents/file/execute", json={"step": _step("api-s7", str(csv_file)), "session_id": "sess-1"})

    response = client.get("/api/v1/agents/file/executions")

    assert response.status_code == 200
    step_ids = {item["step_id"] for item in response.json()["data"]}
    assert "api-s7" in step_ids
