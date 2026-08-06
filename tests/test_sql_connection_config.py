"""Tests for SQLConnectionConfig/DatabaseType and the DatabaseType -> SourceType mapping."""

from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
    source_type_for_database,
)
from backend.ingestion.models.source_type import SourceType


def test_sqlite_config_needs_only_a_database_path() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database="/tmp/data.db")

    assert config.host is None
    assert config.username is None
    assert config.password is None
    assert config.ssl is False
    assert config.timeout == 30.0


def test_password_is_excluded_from_repr() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="db.example.com",
        database="mydb",
        username="user",
        password="super-secret",
    )

    assert "super-secret" not in repr(config)
    assert config.password == "super-secret"  # still a normal, readable field


def test_config_round_trips_through_json() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.MYSQL, host="localhost", port=3306, database="mydb", username="root"
    )

    restored = SQLConnectionConfig.model_validate_json(config.model_dump_json())

    assert restored == config


def test_source_type_for_database_covers_every_database_type() -> None:
    expected = {
        DatabaseType.SQLITE: SourceType.SQLITE,
        DatabaseType.POSTGRESQL: SourceType.POSTGRESQL,
        DatabaseType.MYSQL: SourceType.MYSQL,
        DatabaseType.SQLSERVER: SourceType.SQLSERVER,
        DatabaseType.SNOWFLAKE: SourceType.SNOWFLAKE,
        DatabaseType.BIGQUERY: SourceType.BIGQUERY,
        DatabaseType.DUCKDB: SourceType.DUCKDB,
    }

    for database_type in DatabaseType:
        assert source_type_for_database(database_type) == expected[database_type]
