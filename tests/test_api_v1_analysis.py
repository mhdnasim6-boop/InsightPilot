"""Tests for the /api/v1/analysis endpoint."""

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


def _cleaning_outcome() -> dict:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
    upload = client.post(
        "/api/v1/datasets/upload",
        data={"session_id": session_id},
        files={"file": ("sales.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    ).json()["data"]
    response = client.post(f"/api/v1/datasets/{upload['dataset_id']}/clean")
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def test_analyze_returns_analysis_result() -> None:
    """POSTing a CleaningOutcome should return a fully populated AnalysisResult."""
    outcome = _cleaning_outcome()

    response = client.post("/api/v1/analysis", json=outcome)

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["dataset_id"] == outcome["dataset"]["dataset_id"]
    assert result["dataset_summary"]
    assert isinstance(result["kpis"], list) and len(result["kpis"]) > 0
    assert "trends" in result
    assert "correlations" in result
    assert "anomalies" in result
    assert isinstance(result["insights"], list)
