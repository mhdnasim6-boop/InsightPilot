"""Tests for the /api/v1/agents/sql/* endpoints, against the real app and a
real, temporary SQLite database. Mirrors test_api_v1_file_agent.py.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.main import app

client = TestClient(app)


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE t (a INTEGER, b INTEGER)"))
        connection.execute(text("INSERT INTO t VALUES (1, 2), (3, 4), (5, 6)"))
    engine.dispose()


def _step(step_id: str, db_path: Path, generate_report: bool = False) -> dict:
    return {
        "step_id": step_id,
        "name": "SQL Agent Run",
        "node_name": "sql_agent",
        "inputs": {
            "connection": {"database_type": "sqlite", "database": str(db_path)},
            "table_name": "t",
            "generate_report": generate_report,
        },
    }


def test_execute_returns_a_completed_result(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/agents/sql/execute", json={"step": _step("api-sql-s1", db_path), "session_id": "sess-1"}
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["dataset"]["row_count"] == 3
    assert data["report"] is None
    assert "password" not in data["metadata"]


def test_execute_with_generate_report_populates_report(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/agents/sql/execute",
        json={"step": _step("api-sql-s2", db_path, generate_report=True), "session_id": "sess-1"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["report"] is not None


def test_execute_missing_connection_returns_422() -> None:
    step = {"step_id": "api-sql-s3", "name": "Bad", "node_name": "sql_agent", "inputs": {"table_name": "t"}}

    response = client.post("/api/v1/agents/sql/execute", json={"step": step, "session_id": "sess-1"})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_missing_session_id_returns_422(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post("/api/v1/agents/sql/execute", json={"step": _step("api-sql-s4", db_path)})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_with_both_table_name_and_query_returns_422(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    step = _step("api-sql-s5", db_path)
    step["inputs"]["query"] = "SELECT 1"

    response = client.post("/api/v1/agents/sql/execute", json={"step": step, "session_id": "sess-1"})

    assert response.status_code == 422
    assert response.json()["errors"]["type"] == "InvalidAgentInputError"


def test_execute_on_an_unreachable_database_returns_200_with_a_failed_status() -> None:
    """A pipeline failure is a legitimate, structured result — not an HTTP error."""
    step = {
        "step_id": "api-sql-s6",
        "name": "Bad conn",
        "node_name": "sql_agent",
        "inputs": {"connection": {"database_type": "sqlite", "database": "/no/such/dir/nope.db"}, "table_name": "t"},
    }

    response = client.post("/api/v1/agents/sql/execute", json={"step": step, "session_id": "sess-1"})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["warnings"]


def test_get_execution_fetches_a_previously_run_step(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    client.post("/api/v1/agents/sql/execute", json={"step": _step("api-sql-s7", db_path), "session_id": "sess-1"})

    response = client.get("/api/v1/agents/sql/executions/api-sql-s7")

    assert response.status_code == 200
    assert response.json()["data"]["step_id"] == "api-sql-s7"


def test_get_execution_unknown_step_id_returns_404() -> None:
    response = client.get("/api/v1/agents/sql/executions/does-not-exist")
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "AgentExecutionNotFoundError"


def test_sql_agent_execution_is_also_visible_through_the_file_agent_list_endpoint(tmp_path: Path) -> None:
    """Proves the two agents share one AgentExecutionResultStore, as documented
    in backend/api/v1/sql_agent.py — there is deliberately no
    GET /agents/sql/executions list endpoint for this exact reason."""
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    client.post("/api/v1/agents/sql/execute", json={"step": _step("api-sql-s8", db_path), "session_id": "sess-1"})

    response = client.get("/api/v1/agents/file/executions")

    assert response.status_code == 200
    step_ids = {item["step_id"] for item in response.json()["data"]}
    assert "api-sql-s8" in step_ids
