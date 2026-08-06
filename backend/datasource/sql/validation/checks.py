"""Pure, stateless checks on a connection config's shape — no network I/O.

Reuses ``backend.ingestion.validators.result.ValidationIssue``/
``IssueSeverity`` directly: a structured validation finding is a generic
concept, not an ingestion-specific one, so there is no reason to redefine
an equivalent pair of classes here.
"""

from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)
from backend.ingestion.validators.result import IssueSeverity, ValidationIssue

_FILE_BASED_DATABASE_TYPES = frozenset({DatabaseType.SQLITE, DatabaseType.DUCKDB})


def check_connection_config(config: SQLConnectionConfig) -> list[ValidationIssue]:
    """Flag an obviously-incomplete config before any connection is attempted.

    File-based dialects (SQLite, DuckDB) only need ``database`` (a file
    path); every other dialect needs a host and username too. Malformed
    ``port`` is already impossible to construct (``SQLConnectionConfig``
    enforces the valid range at the model level).
    """
    issues: list[ValidationIssue] = []

    if not config.database.strip():
        issues.append(
            ValidationIssue(severity=IssueSeverity.ERROR, code="missing_database", message="Database is required.")
        )

    if config.database_type not in _FILE_BASED_DATABASE_TYPES:
        if not config.host:
            issues.append(
                ValidationIssue(severity=IssueSeverity.ERROR, code="missing_host", message="Host is required.")
            )
        if not config.username:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR, code="missing_username", message="Username is required."
                )
            )
        if not config.port:
            issues.append(
                ValidationIssue(severity=IssueSeverity.WARNING, code="missing_port", message="No port specified.")
            )

    return issues
