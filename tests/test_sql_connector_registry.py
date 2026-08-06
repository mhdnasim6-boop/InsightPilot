"""Tests for ConnectorRegistry — database-type-keyed dispatch, no if/else chains."""

import pytest

from backend.datasource.sql.connectors.mysql_connector import MySQLConnector
from backend.datasource.sql.connectors.postgres_connector import PostgresConnector
from backend.datasource.sql.connectors.sqlite_connector import SQLiteConnector
from backend.datasource.sql.exceptions.errors import DatabaseNotImplementedError
from backend.datasource.sql.models.connection_config import DatabaseType
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry


@pytest.mark.parametrize(
    ("database_type", "expected_class"),
    [
        (DatabaseType.SQLITE, SQLiteConnector),
        (DatabaseType.POSTGRESQL, PostgresConnector),
        (DatabaseType.MYSQL, MySQLConnector),
    ],
)
def test_get_connector_dispatches_to_the_right_class(database_type: DatabaseType, expected_class: type) -> None:
    connector = ConnectorRegistry().get_connector(database_type)
    assert isinstance(connector, expected_class)


def test_get_connector_returns_a_fresh_instance_each_time() -> None:
    registry = ConnectorRegistry()
    assert registry.get_connector(DatabaseType.SQLITE) is not registry.get_connector(DatabaseType.SQLITE)


@pytest.mark.parametrize(
    "database_type", [DatabaseType.SQLSERVER, DatabaseType.SNOWFLAKE, DatabaseType.BIGQUERY, DatabaseType.DUCKDB]
)
def test_get_connector_raises_not_implemented_for_placeholder_types(database_type: DatabaseType) -> None:
    with pytest.raises(DatabaseNotImplementedError):
        ConnectorRegistry().get_connector(database_type)


def test_available_database_types_excludes_placeholders() -> None:
    available = ConnectorRegistry().available_database_types()

    assert set(available) == {DatabaseType.SQLITE, DatabaseType.POSTGRESQL, DatabaseType.MYSQL}


def test_known_database_types_includes_everything() -> None:
    known = ConnectorRegistry().known_database_types()

    assert set(known) == set(DatabaseType)
