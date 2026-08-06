"""Tests for the /api/v1/datasources/sql/* endpoints, against a real temporary SQLite database."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.main import app

client = TestClient(app)


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, region TEXT)"))
        connection.execute(text("INSERT INTO customers VALUES (1, 'Alice', 'East'), (2, 'Bob', 'West')"))
    engine.dispose()


def _connection(path: Path) -> dict:
    return {"database_type": "sqlite", "database": str(path)}


def test_connect_succeeds_for_a_real_database(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post("/api/v1/datasources/sql/connect", json=_connection(db_path))

    assert response.status_code == 200
    assert response.json()["data"]["is_valid"] is True


def test_connect_reports_failure_for_a_missing_config_field() -> None:
    response = client.post(
        "/api/v1/datasources/sql/connect",
        json={"database_type": "postgresql", "database": "mydb"},  # no host/username
    )

    assert response.status_code == 200  # a structured "not valid" result, not an HTTP error
    data = response.json()["data"]
    assert data["is_valid"] is False
    assert any(issue["code"] == "missing_host" for issue in data["issues"])


def test_list_tables_returns_table_names(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post("/api/v1/datasources/sql/tables", json=_connection(db_path))

    assert response.status_code == 200
    assert response.json()["data"] == ["customers"]


def test_preview_table_returns_rows_and_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/datasources/sql/preview",
        json={"connection": _connection(db_path), "table_name": "customers", "limit": 1},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["preview"]["row_count_previewed"] == 1
    assert data["metadata"]["row_count"] == 2


def test_preview_query_returns_rows_with_no_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/datasources/sql/preview",
        json={"connection": _connection(db_path), "query": "SELECT region, COUNT(*) AS n FROM customers GROUP BY region"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["metadata"] is None
    assert len(data["preview"]["rows"]) == 2


def test_preview_with_both_table_and_query_returns_422(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/datasources/sql/preview",
        json={"connection": _connection(db_path), "table_name": "customers", "query": "SELECT 1"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["status_code"] == 422


def test_preview_with_neither_table_nor_query_returns_422(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post("/api/v1/datasources/sql/preview", json={"connection": _connection(db_path)})

    assert response.status_code == 422


def test_import_table_returns_a_business_dataset_and_registers_it(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/datasources/sql/import/table",
        json={"connection": _connection(db_path), "table_name": "customers", "dataset_name": "sql_customers"},
    )

    assert response.status_code == 200
    dataset = response.json()["data"]
    assert dataset["dataset_name"] == "sql_customers"
    assert dataset["source_type"] == "sqlite"
    assert dataset["row_count"] == 2

    listed = client.get("/api/v1/datasets").json()["data"]
    assert any(entry["dataset_id"] == dataset["dataset_id"] for entry in listed)


def test_import_query_returns_a_business_dataset(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    response = client.post(
        "/api/v1/datasources/sql/import/query",
        json={
            "connection": _connection(db_path),
            "query": "SELECT region, COUNT(*) AS n FROM customers GROUP BY region",
            "dataset_name": "region_counts",
        },
    )

    assert response.status_code == 200
    dataset = response.json()["data"]
    assert dataset["dataset_name"] == "region_counts"
    assert dataset["row_count"] == 2


def test_imported_sql_dataset_flows_through_cleaning_and_analysis(tmp_path: Path) -> None:
    """Proves a SQL-imported dataset needs no special handling anywhere downstream."""
    db_path = tmp_path / "test.db"
    _make_database(db_path)

    dataset = client.post(
        "/api/v1/datasources/sql/import/table", json={"connection": _connection(db_path), "table_name": "customers"}
    ).json()["data"]

    outcome = client.post(f"/api/v1/datasets/{dataset['dataset_id']}/clean").json()["data"]
    assert outcome["dataset"]["row_count"] == 2

    analysis = client.post("/api/v1/analysis", json=outcome).json()["data"]
    assert len(analysis["kpis"]) > 0
