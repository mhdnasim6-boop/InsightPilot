"""Tests for the /api/v1/agents/executive-summary/* endpoints, against the real app
with the real MockProvider. Mirrors test_api_v1_report_agent.py.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _csv(tmp_path: Path, name: str = "t.csv") -> Path:
    path = tmp_path / name
    path.write_text("date,region,revenue\n2024-01-01,East,100\n2024-01-02,West,200\n")
    return path


def _seed_report_document(csv_path: Path, seed_id: str) -> dict:
    file_response = client.post(
        "/api/v1/agents/file/execute",
        json={
            "step": {
                "step_id": f"seed-file-{seed_id}",
                "name": "seed",
                "node_name": "file_agent",
                "inputs": {"dataset_reference": str(csv_path)},
            },
            "session_id": "sess-seed",
        },
    )
    file_data = file_response.json()["data"]

    report_response = client.post(
        "/api/v1/agents/report/execute",
        json={
            "step": {
                "step_id": f"seed-report-{seed_id}",
                "name": "seed",
                "node_name": "report_agent",
                "inputs": {
                    "dataset": file_data["dataset"],
                    "cleaning_outcome": file_data["cleaning"],
                    "analysis_result": file_data["analysis"],
                    "visualization_result": file_data["visualization"],
                },
            },
            "session_id": "sess-seed",
        },
    )
    return report_response.json()["data"]["report_document"]


def _step(step_id: str, report_document: dict, **extra_inputs: object) -> dict:
    return {
        "step_id": step_id,
        "name": "Executive Summary Run",
        "node_name": "executive_summary_agent",
        "inputs": {"report_document": report_document, **extra_inputs},
    }


def test_execute_returns_a_completed_result(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path)
    report_document = _seed_report_document(csv_path, "s1")

    response = client.post(
        "/api/v1/agents/executive-summary/execute",
        json={"step": _step("api-es-s1", report_document), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["executive_summary"]
    assert data["key_findings"]
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["metadata"]["external_context_included"] is False


def test_execute_with_browser_agent_result_marks_external_context_included(
    tmp_path: Path,
) -> None:
    csv_path = _csv(tmp_path, "t2.csv")
    report_document = _seed_report_document(csv_path, "s2")

    browser_response = client.post(
        "/api/v1/agents/browser/execute",
        json={
            "step": {
                "step_id": "seed-browser-s2",
                "name": "seed",
                "node_name": "browser_agent",
                "inputs": {"search_request": "Acme Corp"},
            },
            "session_id": "sess-seed",
        },
    )
    browser_result = browser_response.json()["data"]

    response = client.post(
        "/api/v1/agents/executive-summary/execute",
        json={
            "step": _step(
                "api-es-s2", report_document, browser_agent_result=browser_result
            ),
            "session_id": "sess-1",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["metadata"]["external_context_included"] is True


def test_execute_missing_report_document_returns_422() -> None:
    step = {
        "step_id": "api-es-s3",
        "name": "Bad",
        "node_name": "executive_summary_agent",
        "inputs": {},
    }

    response = client.post(
        "/api/v1/agents/executive-summary/execute",
        json={"step": step, "session_id": "sess-1"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_missing_session_id_returns_422(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path, "t4.csv")
    report_document = _seed_report_document(csv_path, "s4")

    response = client.post(
        "/api/v1/agents/executive-summary/execute",
        json={"step": _step("api-es-s4", report_document)},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_with_an_invalid_browser_agent_result_returns_422(
    tmp_path: Path,
) -> None:
    csv_path = _csv(tmp_path, "t5.csv")
    report_document = _seed_report_document(csv_path, "s5")

    response = client.post(
        "/api/v1/agents/executive-summary/execute",
        json={
            "step": _step(
                "api-es-s5",
                report_document,
                browser_agent_result={"not": "a real browser result"},
            ),
            "session_id": "sess-1",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_get_execution_fetches_a_previously_run_step(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path, "t6.csv")
    report_document = _seed_report_document(csv_path, "s6")
    client.post(
        "/api/v1/agents/executive-summary/execute",
        json={"step": _step("api-es-s6", report_document), "session_id": "sess-1"},
    )

    response = client.get("/api/v1/agents/executive-summary/executions/api-es-s6")

    assert response.status_code == 200
    assert response.json()["data"]["step_id"] == "api-es-s6"


def test_get_execution_unknown_step_id_returns_404() -> None:
    response = client.get("/api/v1/agents/executive-summary/executions/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "AgentExecutionNotFoundError"


def test_executive_summary_execution_is_not_visible_through_the_report_agent_store(
    tmp_path: Path,
) -> None:
    """Proves ExecutiveSummaryAgent has its own, separate ExecutiveSummaryResultStore -
    the same step_id is unknown to ReportAgentService's own store."""
    csv_path = _csv(tmp_path, "t7.csv")
    report_document = _seed_report_document(csv_path, "s7")
    client.post(
        "/api/v1/agents/executive-summary/execute",
        json={"step": _step("api-es-s7", report_document), "session_id": "sess-1"},
    )

    response = client.get("/api/v1/agents/report/executions/api-es-s7")

    assert response.status_code == 404
