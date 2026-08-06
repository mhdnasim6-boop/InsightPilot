"""Tests for the /api/v1/datasets endpoints (upload+ingest, list, get, clean)."""

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


def _create_session() -> str:
    response = client.post("/api/v1/sessions")
    return str(response.json()["data"]["session_id"])


def _upload_dataset(session_id: str, filename: str = "sales.csv") -> dict:
    response = client.post(
        "/api/v1/datasets/upload",
        data={"session_id": session_id},
        files={"file": (filename, io.BytesIO(CSV_BYTES), "text/csv")},
    )
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def test_upload_dataset_ingests_and_returns_metadata() -> None:
    """Uploading a CSV should ingest it and return a BusinessDataset with correct shape."""
    session_id = _create_session()

    dataset = _upload_dataset(session_id)

    assert dataset["dataset_id"]
    assert dataset["row_count"] == 4
    assert dataset["column_count"] == 3


def test_list_datasets_includes_uploaded_dataset() -> None:
    """Listing datasets should surface a dataset just uploaded."""
    session_id = _create_session()
    dataset = _upload_dataset(session_id)

    response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    dataset_ids = [item["dataset_id"] for item in response.json()["data"]]
    assert dataset["dataset_id"] in dataset_ids


def test_get_dataset_by_id() -> None:
    """Fetching a dataset by ID should return the same dataset."""
    session_id = _create_session()
    dataset = _upload_dataset(session_id)

    response = client.get(f"/api/v1/datasets/{dataset['dataset_id']}")

    assert response.status_code == 200
    assert response.json()["data"]["dataset_id"] == dataset["dataset_id"]


def test_get_missing_dataset_returns_404() -> None:
    """Fetching an unknown dataset_id should use the unified error envelope."""
    response = client.get("/api/v1/datasets/does-not-exist")

    assert response.status_code == 404
    assert response.json()["errors"]["status_code"] == 404


def test_clean_dataset_returns_outcome_and_updates_store() -> None:
    """Cleaning a dataset should return a CleaningOutcome and re-store the cleaned dataset."""
    session_id = _create_session()
    dataset = _upload_dataset(session_id)

    response = client.post(f"/api/v1/datasets/{dataset['dataset_id']}/clean")

    assert response.status_code == 200
    outcome = response.json()["data"]
    assert outcome["dataset"]["dataset_id"]
    assert outcome["result"]["rows_after"] == 4

    fetched = client.get(f"/api/v1/datasets/{outcome['dataset']['dataset_id']}")
    assert fetched.status_code == 200


def test_clean_missing_dataset_returns_404() -> None:
    """Cleaning an unknown dataset_id should use the unified error envelope."""
    response = client.post("/api/v1/datasets/does-not-exist/clean")

    assert response.status_code == 404
    assert response.json()["errors"]["status_code"] == 404
