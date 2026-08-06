"""Tests for the /api/v1/reports/* endpoints, chained over real HTTP calls
(upload -> clean -> analyze -> visualize -> report), matching the pattern
already established in test_api_v1_chat.py and test_api_v1_sql_datasource.py.
"""

import io

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

CSV_BYTES = (
    b"date,region,revenue,cost\n"
    b"2024-01-01,East,1000,600\n"
    b"2024-02-01,East,1100,650\n"
    b"2024-03-01,East,1180,680\n"
    b"2024-01-01,West,200,120\n"
    b"2024-02-01,West,210,130\n"
    b"2024-03-01,West,9000,5000\n"
)


def _pipeline_outputs() -> dict:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
    upload = client.post(
        "/api/v1/datasets/upload",
        data={"session_id": session_id},
        files={"file": ("sales.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    ).json()["data"]
    outcome = client.post(f"/api/v1/datasets/{upload['dataset_id']}/clean").json()["data"]
    analysis = client.post("/api/v1/analysis", json=outcome).json()["data"]
    visualization = client.post(
        "/api/v1/visualizations", json={"analysis_result": analysis, "dataset": outcome["dataset"]}
    ).json()["data"]["visualization_result"]
    return {"cleaning_outcome": outcome, "analysis_result": analysis, "visualization_result": visualization}


def test_generate_report_returns_a_document_with_expected_sections() -> None:
    outputs = _pipeline_outputs()

    response = client.post(
        "/api/v1/reports",
        json={
            "dataset": outputs["cleaning_outcome"]["dataset"],
            "cleaning_outcome": outputs["cleaning_outcome"],
            "analysis_result": outputs["analysis_result"],
            "visualization_result": outputs["visualization_result"],
            "template_type": "business_report",
        },
    )

    assert response.status_code == 200, response.text
    document = response.json()["data"]
    assert document["report_id"]
    section_ids = {section["section_id"] for section in document["sections"]}
    assert {"overview", "kpis", "charts"} <= section_ids


def test_generate_report_defaults_to_business_report_template() -> None:
    outputs = _pipeline_outputs()

    response = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["metadata"]["template_type"] == "business_report"


def test_generate_report_returns_422_when_a_required_section_is_missing() -> None:
    outputs = _pipeline_outputs()

    response = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "template_type": "technical_report"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["status_code"] == 422


def test_get_report_fetches_a_previously_generated_report() -> None:
    outputs = _pipeline_outputs()
    created = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    ).json()["data"]

    response = client.get(f"/api/v1/reports/{created['report_id']}")

    assert response.status_code == 200
    assert response.json()["data"]["report_id"] == created["report_id"]


def test_get_report_returns_404_for_an_unknown_id() -> None:
    response = client.get("/api/v1/reports/does-not-exist")
    assert response.status_code == 404


def test_list_reports_includes_a_newly_generated_report() -> None:
    outputs = _pipeline_outputs()
    created = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    ).json()["data"]

    listed = client.get("/api/v1/reports").json()["data"]

    assert any(report["report_id"] == created["report_id"] for report in listed)


def test_list_report_templates_returns_all_five() -> None:
    response = client.get("/api/v1/reports/templates")

    assert response.status_code == 200
    assert set(response.json()["data"]) == {
        "executive_summary",
        "business_report",
        "technical_report",
        "data_quality_report",
        "comparison_report",
    }


def test_list_report_themes_returns_all_four_built_ins() -> None:
    response = client.get("/api/v1/reports/themes")

    assert response.status_code == 200
    assert set(response.json()["data"]) == {"corporate", "modern", "minimal", "dark"}


def test_export_report_as_json() -> None:
    outputs = _pipeline_outputs()
    created = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    ).json()["data"]

    response = client.get(f"/api/v1/reports/{created['report_id']}/export", params={"format": "json"})

    assert response.status_code == 200
    content = response.json()["data"]
    assert isinstance(content, str)
    assert created["report_id"] in content


def test_export_report_as_markdown() -> None:
    outputs = _pipeline_outputs()
    created = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    ).json()["data"]

    response = client.get(f"/api/v1/reports/{created['report_id']}/export", params={"format": "markdown"})

    assert response.status_code == 200
    content = response.json()["data"]
    assert content.startswith(f"# {created['title']}")


def test_export_report_defaults_to_json_format() -> None:
    outputs = _pipeline_outputs()
    created = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    ).json()["data"]

    response = client.get(f"/api/v1/reports/{created['report_id']}/export")

    assert response.status_code == 200
    content = response.json()["data"]
    assert created["report_id"] in content


def test_export_report_rejects_an_unsupported_format() -> None:
    outputs = _pipeline_outputs()
    created = client.post(
        "/api/v1/reports",
        json={"dataset": outputs["cleaning_outcome"]["dataset"], "analysis_result": outputs["analysis_result"]},
    ).json()["data"]

    response = client.get(f"/api/v1/reports/{created['report_id']}/export", params={"format": "pdf"})

    assert response.status_code == 422  # not one of the Literal["json", "markdown"] values


def test_export_report_returns_404_for_an_unknown_id() -> None:
    response = client.get("/api/v1/reports/does-not-exist/export")
    assert response.status_code == 404
