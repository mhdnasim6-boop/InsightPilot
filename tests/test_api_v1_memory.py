"""Tests for the /api/v1/memory/* endpoints, against the real app.

``MemoryStore`` is a process-wide DI singleton shared by the whole test
suite via ``TestClient(app)`` (same reasoning as ``test_api_v1_approvals.py``'s
own ``ApprovalPolicyService``) — the ``_clear_memory`` fixture empties it
before every test here so counts/searches in this file are never
polluted by other test files' own memories.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.memory import get_memory_store
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_memory() -> Iterator[None]:
    get_memory_store().clear()
    yield
    get_memory_store().clear()


def _create_memory(title: str = "Sales Dataset", memory_type: str = "dataset", **overrides: object) -> dict:
    payload = {"title": title, "summary": "A test memory.", "memory_type": memory_type}
    payload.update(overrides)
    response = client.post("/api/v1/memory", json=payload)
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def test_create_and_get_memory() -> None:
    created = _create_memory()
    response = client.get(f"/api/v1/memory/{created['memory_id']}")
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Sales Dataset"


def test_list_memories_returns_every_created_memory() -> None:
    _create_memory("First")
    _create_memory("Second")
    response = client.get("/api/v1/memory")
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["data"]}
    assert titles == {"First", "Second"}


def test_get_unknown_memory_returns_404() -> None:
    response = client.get("/api/v1/memory/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "MemoryItemNotFoundError"


def test_delete_memory() -> None:
    created = _create_memory()
    response = client.delete(f"/api/v1/memory/{created['memory_id']}")
    assert response.status_code == 200
    assert response.json()["data"] is True
    assert client.get(f"/api/v1/memory/{created['memory_id']}").status_code == 404


def test_search_memories_by_keyword() -> None:
    _create_memory("Sales Dataset", memory_type="dataset")
    _create_memory("Marketing Report", memory_type="report")

    response = client.post("/api/v1/memory/search", json={"keyword": "sales", "top_k": 5})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_matched"] == 1
    assert data["items"][0]["title"] == "Sales Dataset"


def test_search_memories_by_type_and_scope() -> None:
    _create_memory("A", memory_type="dataset", scope="session")
    _create_memory("B", memory_type="report", scope="project")

    response = client.post("/api/v1/memory/search", json={"memory_type": "report", "scope": "project"})

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["data"]["items"]]
    assert titles == ["B"]


def test_summarize_memories() -> None:
    _create_memory("First")
    _create_memory("Second")

    response = client.post("/api/v1/memory/summarize", json={})

    assert response.status_code == 200
    assert "First" in response.json()["data"]
    assert "Second" in response.json()["data"]


def test_get_statistics() -> None:
    _create_memory("A", memory_type="dataset")
    _create_memory("B", memory_type="report")

    response = client.get("/api/v1/memory/statistics")

    assert response.status_code == 200
    stats = response.json()["data"]
    assert stats["total_items"] == 2
    assert stats["by_type"] == {"dataset": 1, "report": 1}


@pytest.mark.parametrize(("export_format", "expected_snippet"), [("json", '"title"'), ("markdown", "# Memory Export")])
def test_export_memories(export_format: str, expected_snippet: str) -> None:
    _create_memory()

    response = client.get(f"/api/v1/memory/export/{export_format}")

    assert response.status_code == 200
    assert expected_snippet in response.json()["data"]


def test_clear_all_memories() -> None:
    _create_memory("First")
    _create_memory("Second")

    response = client.delete("/api/v1/memory")

    assert response.status_code == 200
    assert response.json()["data"] is True
    assert client.get("/api/v1/memory").json()["data"] == []
