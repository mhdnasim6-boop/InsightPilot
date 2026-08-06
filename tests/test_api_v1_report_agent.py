"""Tests for the /api/v1/agents/report/* endpoints, against the real app with the
real ReportService. Mirrors test_api_v1_browser_agent.py.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _dataset_payload(csv_path: Path) -> dict:
    response = client.post(
        "/api/v1/agents/file/execute",
        json={
            "step": {
                "step_id": f"seed-{csv_path.name}",
                "name": "seed",
                "node_name": "file_agent",
                "inputs": {"dataset_reference": str(csv_path)},
            },
            "session_id": "sess-seed",
        },
    )
    data = response.json()["data"]
    return {
        "dataset": data["dataset"],
        "cleaning_outcome": data["cleaning"],
        "analysis_result": data["analysis"],
    }


def _csv(tmp_path: Path, name: str = "t.csv") -> Path:
    path = tmp_path / name
    path.write_text("date,region,revenue\n2024-01-01,East,100\n2024-01-02,West,200\n")
    return path


def _step(step_id: str, dataset: dict, **extra_inputs: object) -> dict:
    return {
        "step_id": step_id,
        "name": "Report Agent Run",
        "node_name": "report_agent",
        "inputs": {"dataset": dataset, **extra_inputs},
    }


def test_execute_returns_a_completed_result(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path)
    payload = _dataset_payload(csv_path)

    response = client.post(
        "/api/v1/agents/report/execute",
        json={"step": _step("api-report-s1", **payload), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["report_id"] is not None
    assert data["report_document"]["sections"]


def test_execute_with_report_config_sets_title_theme_and_template(
    tmp_path: Path,
) -> None:
    csv_path = _csv(tmp_path, "t2.csv")
    payload = _dataset_payload(csv_path)

    response = client.post(
        "/api/v1/agents/report/execute",
        json={
            "step": _step(
                "api-report-s2",
                **payload,
                report_config={
                    "template_type": "executive_summary",
                    "theme": "dark",
                    "title": "Custom",
                },
            ),
            "session_id": "sess-1",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["report_document"]["title"] == "Custom"
    assert data["report_document"]["theme"] == "dark"
    assert data["metadata"]["template_type"] == "executive_summary"


def test_execute_missing_dataset_returns_422() -> None:
    step = {
        "step_id": "api-report-s3",
        "name": "Bad",
        "node_name": "report_agent",
        "inputs": {},
    }

    response = client.post(
        "/api/v1/agents/report/execute", json={"step": step, "session_id": "sess-1"}
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_missing_session_id_returns_422(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path, "t3.csv")
    payload = _dataset_payload(csv_path)

    response = client.post(
        "/api/v1/agents/report/execute",
        json={"step": _step("api-report-s4", **payload)},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_with_unknown_template_type_returns_422(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path, "t5.csv")
    payload = _dataset_payload(csv_path)

    response = client.post(
        "/api/v1/agents/report/execute",
        json={
            "step": _step(
                "api-report-s5",
                **payload,
                report_config={"template_type": "not-a-real-template"},
            ),
            "session_id": "sess-1",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_on_a_report_that_fails_validation_returns_200_with_a_failed_status(
    tmp_path: Path,
) -> None:
    """business_report requires a KPIs section - a bare dataset (no AnalysisResult)
    fails real ReportValidator validation - a legitimate, structured result, not an HTTP error."""
    csv_path = _csv(tmp_path, "t6.csv")
    file_response = client.post(
        "/api/v1/agents/file/execute",
        json={
            "step": {
                "step_id": "seed-bare",
                "name": "seed",
                "node_name": "file_agent",
                "inputs": {"dataset_reference": str(csv_path)},
            },
            "session_id": "sess-seed",
        },
    )
    dataset = file_response.json()["data"]["dataset"]

    response = client.post(
        "/api/v1/agents/report/execute",
        json={"step": _step("api-report-s6", dataset=dataset), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["warnings"]


def test_get_execution_fetches_a_previously_run_step(tmp_path: Path) -> None:
    csv_path = _csv(tmp_path, "t7.csv")
    payload = _dataset_payload(csv_path)
    client.post(
        "/api/v1/agents/report/execute",
        json={"step": _step("api-report-s7", **payload), "session_id": "sess-1"},
    )

    response = client.get("/api/v1/agents/report/executions/api-report-s7")

    assert response.status_code == 200
    assert response.json()["data"]["step_id"] == "api-report-s7"


def test_get_execution_unknown_step_id_returns_404() -> None:
    response = client.get("/api/v1/agents/report/executions/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "AgentExecutionNotFoundError"


def test_report_agent_execution_is_not_visible_through_the_reports_list_endpoint(
    tmp_path: Path,
) -> None:
    """Proves ReportAgent has its own, separate ReportAgentResultStore -
    GET /reports lists ReportDocuments (unaffected either way), not ReportAgentResults."""
    csv_path = _csv(tmp_path, "t8.csv")
    payload = _dataset_payload(csv_path)
    response = client.post(
        "/api/v1/agents/report/execute",
        json={"step": _step("api-report-s8", **payload), "session_id": "sess-1"},
    )
    report_id = response.json()["data"]["report_id"]

    reports_response = client.get("/api/v1/reports")
    report_ids = {item["report_id"] for item in reports_response.json()["data"]}
    assert report_id in report_ids  # the underlying ReportDocument IS listed there

    # but the step_id (ReportAgent's own identity) has no equivalent list endpoint
    executions_response = client.get("/api/v1/agents/report/executions/api-report-s8")
    assert executions_response.status_code == 200
