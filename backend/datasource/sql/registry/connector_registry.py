"""Maps a ``DatabaseType`` to a connector.

Mirrors ``backend.ingestion.registry.loader_registry.LoaderRegistry``
exactly: a plain dict dispatch table (no if/else chains) plus a frozenset
of database types that are recognized concepts (SQL Server, Snowflake,
BigQuery, DuckDB) with no connector implementation yet. Adding a real
connector for one of those later means moving its type from
``_PLACEHOLDER_TYPES`` into ``_REGISTRY`` — nothing else in the SQL data
source layer changes.
"""

from collections.abc import Callable

from backend.datasource.sql.connectors.base import SQLConnector
from backend.datasource.sql.connectors.mysql_connector import MySQLConnector
from backend.datasource.sql.connectors.postgres_connector import PostgresConnector
from backend.datasource.sql.connectors.sqlite_connector import SQLiteConnector
from backend.datasource.sql.exceptions.errors import (
    DatabaseNotImplementedError,
    UnsupportedDatabaseError,
)
from backend.datasource.sql.models.connection_config import DatabaseType

_REGISTRY: dict[DatabaseType, Callable[[], SQLConnector]] = {
    DatabaseType.SQLITE: SQLiteConnector,
    DatabaseType.POSTGRESQL: PostgresConnector,
    DatabaseType.MYSQL: MySQLConnector,
}

# Recognized database types with no connector implementation in this phase.
_PLACEHOLDER_TYPES: frozenset[DatabaseType] = frozenset(
    {DatabaseType.SQLSERVER, DatabaseType.SNOWFLAKE, DatabaseType.BIGQUERY, DatabaseType.DUCKDB}
)


class ConnectorRegistry:
    """Resolves a ``DatabaseType`` to a fresh, unconnected ``SQLConnector`` instance."""

    def get_connector(self, database_type: DatabaseType) -> SQLConnector:
        """Return a new connector for ``database_type``.

        Raises ``DatabaseNotImplementedError`` for a recognized-but-not-
        yet-implemented type, or ``UnsupportedDatabaseError`` for one
        InsightPilot doesn't recognize at all.
        """
        if database_type in _PLACEHOLDER_TYPES:
            raise DatabaseNotImplementedError(f"Database type '{database_type.value}' is recognized but not implemented yet.")

        builder = _REGISTRY.get(database_type)
        if builder is None:
            raise UnsupportedDatabaseError(f"Unsupported database type: '{database_type.value}'.")
        return builder()

    def available_database_types(self) -> list[DatabaseType]:
        """Database types that can actually be connected to today."""
        return sorted(_REGISTRY, key=lambda database_type: database_type.value)

    def known_database_types(self) -> list[DatabaseType]:
        """Every database type InsightPilot recognizes, implemented or not."""
        return sorted({*_REGISTRY, *_PLACEHOLDER_TYPES}, key=lambda database_type: database_type.value)
