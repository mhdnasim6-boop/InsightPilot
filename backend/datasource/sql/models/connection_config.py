"""SQL connection configuration.

``DatabaseType`` is deliberately its own enum, not a reuse of
``backend.ingestion.models.source_type.SourceType`` — a
``SQLConnectionConfig`` should only ever be constructible with a value
that actually means "a database dialect" (making
``SQLConnectionConfig(database_type=SourceType.CSV, ...)`` a type error,
not a runtime surprise). :func:`source_type_for_database` bridges the two
when a successful import needs to stamp a ``BusinessDataset.source_type``.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.ingestion.models.source_type import SourceType


class DatabaseType(str, Enum):
    """Every SQL dialect InsightPilot recognizes, implemented or not."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    DUCKDB = "duckdb"


_DATABASE_SOURCE_TYPES: dict[DatabaseType, SourceType] = {
    DatabaseType.SQLITE: SourceType.SQLITE,
    DatabaseType.POSTGRESQL: SourceType.POSTGRESQL,
    DatabaseType.MYSQL: SourceType.MYSQL,
    DatabaseType.SQLSERVER: SourceType.SQLSERVER,
    DatabaseType.SNOWFLAKE: SourceType.SNOWFLAKE,
    DatabaseType.BIGQUERY: SourceType.BIGQUERY,
    DatabaseType.DUCKDB: SourceType.DUCKDB,
}


def source_type_for_database(database_type: DatabaseType) -> SourceType:
    """Map a ``DatabaseType`` to its ``BusinessDataset``-facing ``SourceType``."""
    return _DATABASE_SOURCE_TYPES[database_type]


class SQLConnectionConfig(BaseModel):
    """Everything needed to connect to a SQL database, for any supported dialect.

    ``host``/``port``/``username``/``password`` are optional because
    SQLite is file-based — ``database`` alone (a file path, or
    ``":memory:"``) is enough for it. ``password`` is excluded from
    ``repr()`` so it can never leak into a log line via
    ``logger.info(config)``; it is still a normal field otherwise (it must
    round-trip through the API request that carries it).
    """

    database_type: DatabaseType
    host: str | None = None
    port: int | None = Field(default=None, gt=0, le=65535)
    database: str
    username: str | None = None
    password: str | None = Field(default=None, repr=False)
    ssl: bool = False
    timeout: float = Field(default=30.0, gt=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
