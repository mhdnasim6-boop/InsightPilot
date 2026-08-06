"""Tests for check_connection_config — config-shape validation, no network I/O."""

from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)
from backend.datasource.sql.validation.checks import check_connection_config


def test_sqlite_config_needs_only_database() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database="/tmp/data.db")

    assert check_connection_config(config) == []


def test_sqlite_config_missing_database_is_an_error() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.SQLITE, database="")

    issues = check_connection_config(config)

    assert any(issue.code == "missing_database" for issue in issues)


def test_postgres_config_missing_host_and_username_are_errors() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.POSTGRESQL, database="mydb")

    issues = check_connection_config(config)

    codes = {issue.code for issue in issues}
    assert "missing_host" in codes
    assert "missing_username" in codes


def test_postgres_config_missing_port_is_a_warning_not_an_error() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.POSTGRESQL, host="db.example.com", database="mydb", username="user"
    )

    issues = check_connection_config(config)

    assert len(issues) == 1
    assert issues[0].code == "missing_port"
    assert issues[0].severity.value == "warning"


def test_well_formed_postgres_config_has_no_issues() -> None:
    config = SQLConnectionConfig(
        database_type=DatabaseType.POSTGRESQL,
        host="db.example.com",
        port=5432,
        database="mydb",
        username="user",
        password="pass",
    )

    assert check_connection_config(config) == []


def test_mysql_config_follows_the_same_rules_as_postgres() -> None:
    config = SQLConnectionConfig(database_type=DatabaseType.MYSQL, database="mydb")

    issues = check_connection_config(config)

    codes = {issue.code for issue in issues}
    assert "missing_host" in codes
    assert "missing_username" in codes
