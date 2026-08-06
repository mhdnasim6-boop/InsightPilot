"""Tests for the /api/v1/chat endpoint."""

import io

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

CSV_BYTES = (
    b"date,region,revenue\n"
    b"2024-01-01,East,100\n"
    b"2024-02-01,East,150\n"
    b"2024-01-01,West,50\n"
    b"2024-02-01,West,9000\n"
)


def _analyzed_context() -> dict:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
    upload = client.post(
        "/api/v1/datasets/upload",
        data={"session_id": session_id},
        files={"file": ("sales.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    ).json()["data"]
    outcome = client.post(f"/api/v1/datasets/{upload['dataset_id']}/clean").json()["data"]
    analysis = client.post("/api/v1/analysis", json=outcome).json()["data"]
    return {
        "session_id": session_id,
        "selected_dataset": outcome["dataset"],
        "cleaning_outcome": outcome,
        "analysis_result": analysis,
    }


def test_ask_chat_answers_kpi_question() -> None:
    context = _analyzed_context()

    response = client.post("/api/v1/chat", json={"question": "What are the KPIs?", "context": context})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["intent"] == "kpi"
    assert data["answerable"] is True
    assert data["confidence"] == 1.0
    assert len(data["referenced_kpis"]) > 0
    assert data["referenced_datasets"] == ["sales.csv"]


def test_ask_chat_refuses_when_context_is_empty() -> None:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]

    response = client.post(
        "/api/v1/chat", json={"question": "What are the KPIs?", "context": {"session_id": session_id}}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answerable"] is False
    assert data["confidence"] == 0.0
    assert "analyzed" in data["answer"]


def test_ask_chat_general_question_never_fails_even_with_no_dataset() -> None:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]

    response = client.post(
        "/api/v1/chat", json={"question": "hello, what can you do?", "context": {"session_id": session_id}}
    )

    assert response.status_code == 200
    assert response.json()["data"]["answerable"] is True


def test_ask_chat_conversation_history_round_trips() -> None:
    context = _analyzed_context()
    context["conversation_history"] = [
        {"role": "user", "content": "What dataset is this?", "timestamp": "2026-01-01T00:00:00Z"}
    ]

    response = client.post("/api/v1/chat", json={"question": "What are the KPIs?", "context": context})

    assert response.status_code == 200
    assert "What dataset is this?" in response.json()["data"]["answer"]


def test_ask_chat_missing_question_returns_422() -> None:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]

    response = client.post("/api/v1/chat", json={"context": {"session_id": session_id}})

    assert response.status_code == 422
    assert response.json()["errors"]["status_code"] == 422
