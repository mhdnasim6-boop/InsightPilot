"""Tests for the /api/v1/visualizations endpoint."""

import io

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

CSV_BYTES = (
    b"date,region,revenue\n"
    b"2024-01-01,East,100\n"
    b"2024-02-01,East,150\n"
    b"2024-01-01,West,50\n"
    b"2024-02-01,West,90\n"
)


def _analysis_result() -> tuple[dict, dict]:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
    upload = client.post(
        "/api/v1/datasets/upload",
        data={"session_id": session_id},
        files={"file": ("sales.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    ).json()["data"]
    outcome = client.post(f"/api/v1/datasets/{upload['dataset_id']}/clean").json()["data"]
    analysis = client.post("/api/v1/analysis", json=outcome).json()["data"]
    return analysis, outcome["dataset"]


def test_generate_visualizations_renders_charts() -> None:
    """A valid AnalysisResult should produce charts pre-rendered to Plotly figure JSON."""
    analysis, dataset = _analysis_result()

    response = client.post(
        "/api/v1/visualizations",
        json={
            "analysis_result": analysis,
            "dataset": dataset,
            "layout_type": "detailed_analysis",
            "theme": "dark",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    charts = body["visualization_result"]["charts"]
    assert len(charts) > 0

    rendered = body["rendered_charts"]
    chart_ids = {chart["chart_id"] for chart in charts}
    assert set(rendered.keys()) == chart_ids
    for figure_json in rendered.values():
        assert "data" in figure_json
        assert "layout" in figure_json


def test_generate_visualizations_unknown_theme_returns_404() -> None:
    """An unrecognized theme name should propagate as a 404, not a silent fallback."""
    analysis, dataset = _analysis_result()

    response = client.post(
        "/api/v1/visualizations",
        json={"analysis_result": analysis, "dataset": dataset, "theme": "does-not-exist"},
    )

    assert response.status_code == 404
    assert response.json()["errors"]["status_code"] == 404
