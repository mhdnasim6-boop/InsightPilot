"""Tests for SQLConnector implementations.

SQLite is tested against a real, temporary database file — no server to
mock, so there is no reason not to exercise it for real. PostgreSQL and
MySQL have no server available in this environment ("mock
PostgreSQL/MySQL, no external servers"): rather than hand-rolling a fake
engine, their *own* distinctive logic (URL/connect_args construction) is
tested directly with no I/O at all, and their connection-*failure* path
is tested against a real, deliberately unreachable local port
(``127.0.0.1:1`` — nothing listens there) — this fails in well under a
second and exercises the real ``psycopg2``/``pymysql`` drivers and real
``sqlalchemy.exc`` handling, which a hand-written mock could not. Every
other method (list_tables/describe_table/execute_query/preview/validate)
is concrete, shared base-class code already fully covered by the SQLite
tests below — Postgres/MySQL inherit it unchanged.
"""

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from backend.datasource.sql.connectors.mysql_connector import MySQLConnector
from backend.datasource.sql.connectors.postgres_connector import PostgresConnector
from backend.datasource.sql.connectors.sqlite_connector import SQLiteConnector
from backend.datasource.sql.exceptions.errors import (
    ConnectionFailedError,
    QueryExecutionError,
    TableNotFoundError,
)
from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)

_UNREACHABLE_HOST = "127.0.0.1"
_UNREACHABLE_PORT = 1  # nothing listens here; connection is refused near-instantly


def _make_database(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, region TEXT)"))
        connection.execute(text("INSERT INTO customers VALUES (1, 'Alice', 'East'), (2, 'Bob', 'West')"))
    engine.dispose()


# -- SQLiteConnector: real database, full lifecycle --------------------------


def test_sqlite_connector_full_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))
    connector = SQLiteConnector()

    assert connector.database_type == DatabaseType.SQLITE

    connector.connect(config)
    try:
        assert connector.list_tables() == ["customers"]

        metadata = connector.describe_table("customers")
        assert metadata.row_count == 2

        preview = connector.preview("customers", limit=1)
        assert preview.row_count_previewed == 1
        assert preview.rows[0]["name"] == "Alice"

        full = connector.read_table("customers")
        assert isinstance(full, pd.DataFrame)
        assert len(full) == 2

        result = connector.execute_query("SELECT region, COUNT(*) AS n FROM customers GROUP BY region")
        assert set(result["region"]) == {"East", "West"}
    finally:
        connector.disconnect()


def test_sqlite_connector_validate_succeeds_without_a_prior_connect(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))

    result = SQLiteConnector().validate(config)

    assert result.is_valid is True
    assert result.database_type == DatabaseType.SQLITE


def test_sqlite_connector_describe_missing_table_raises_table_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))
    connector = SQLiteConnector()
    connector.connect(config)

    with pytest.raises(TableNotFoundError):
        connector.describe_table("nonexistent")

    connector.disconnect()


def test_sqlite_connector_preview_missing_table_raises_table_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))
    connector = SQLiteConnector()
    connector.connect(config)

    with pytest.raises(TableNotFoundError):
        connector.preview("nonexistent")

    connector.disconnect()


def test_sqlite_connector_execute_query_wraps_bad_sql_as_query_execution_error(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))
    connector = SQLiteConnector()
    connector.connect(config)

    with pytest.raises(QueryExecutionError):
        connector.execute_query("SELECT this is not valid sql")

    connector.disconnect()


def test_sqlite_connector_methods_require_connect_first(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    connector = SQLiteConnector()

    with pytest.raises(ConnectionFailedError):
        connector.list_tables()


def test_sqlite_connector_disconnect_is_safe_to_call_twice(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    _make_database(db_path)
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database=str(db_path))
    connector = SQLiteConnector()
    connector.connect(config)

    connector.disconnect()
    connector.disconnect()  # must not raise


# -- PostgresConnector: URL/connect_args construction, no I/O ----------------


def test_postgres_connector_builds_expected_url_and_hides_password() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="db.example.com",
        port=5433,
        database="mydb",
        username="user",
        password="secret",
    )
    connector = PostgresConnector()

    url = connector._build_url(config)

    assert connector.database_type == DatabaseType.POSTGRESQL
    assert url.render_as_string(hide_password=True) == "postgresql+psycopg2://user:***@db.example.com:5433/mydb"


def test_postgres_connector_applies_default_port_when_not_given() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.POSTGRESQL, host="db.example.com", database="mydb")
    connector = PostgresConnector()

    url = connector._build_url(config)

    assert url.port == 5432


def test_postgres_connector_connect_args_include_sslmode_only_when_ssl_enabled() -> None:
    connector = PostgresConnector()
    base_config = SQLConnectionConfig(database_type=DatabaseType.POSTGRESQL, host="h", database="d", timeout=5)

    assert connector._connect_args(base_config) == {"connect_timeout": 5}
    ssl_config = base_config.model_copy(update={"ssl": True})
    assert connector._connect_args(ssl_config) == {"connect_timeout": 5, "sslmode": "require"}


def test_postgres_connector_connect_fails_fast_against_an_unreachable_host() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.POSTGRESQL,
        host=_UNREACHABLE_HOST,
        port=_UNREACHABLE_PORT,
        database="db",
        username="user",
        password="pass",
        timeout=2,
    )

    with pytest.raises(ConnectionFailedError):
        PostgresConnector().connect(config)


def test_postgres_connector_validate_reports_failure_against_an_unreachable_host() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.POSTGRESQL,
        host=_UNREACHABLE_HOST,
        port=_UNREACHABLE_PORT,
        database="db",
        username="user",
        password="pass",
        timeout=2,
    )

    result = PostgresConnector().validate(config)

    assert result.is_valid is False
    assert "Connection failed" in result.message


# -- MySQLConnector: URL/connect_args construction, no I/O -------------------


def test_mysql_connector_builds_expected_url_and_hides_password() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.MYSQL,
        host="db.example.com",
        port=3307,
        database="mydb",
        username="root",
        password="secret",
    )
    connector = MySQLConnector()

    url = connector._build_url(config)

    assert connector.database_type == DatabaseType.MYSQL
    assert url.render_as_string(hide_password=True) == "mysql+pymysql://root:***@db.example.com:3307/mydb"


def test_mysql_connector_applies_default_port_when_not_given() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.MYSQL, host="db.example.com", database="mydb")
    connector = MySQLConnector()

    url = connector._build_url(config)

    assert url.port == 3306


def test_mysql_connector_connect_args_include_ssl_only_when_enabled() -> None:
    connector = MySQLConnector()
    base_config = SQLConnectionConfig(database_type=DatabaseType.MYSQL, host="h", database="d", timeout=5)

    assert connector._connect_args(base_config) == {"connect_timeout": 5}
    ssl_config = base_config.model_copy(update={"ssl": True})
    assert connector._connect_args(ssl_config) == {"connect_timeout": 5, "ssl": {}}


def test_mysql_connector_connect_fails_fast_against_an_unreachable_host() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.MYSQL,
        host=_UNREACHABLE_HOST,
        port=_UNREACHABLE_PORT,
        database="db",
        username="root",
        password="pass",
        timeout=2,
    )

    with pytest.raises(ConnectionFailedError):
        MySQLConnector().connect(config)
