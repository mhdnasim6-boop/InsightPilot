"""PostgreSQL connector, via SQLAlchemy's ``psycopg2`` dialect."""

from typing import Any

from sqlalchemy.engine import URL

from backend.datasource.sql.connectors.base import SQLConnector
from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)

_DEFAULT_PORT = 5432


class PostgresConnector(SQLConnector):
    """Connects to PostgreSQL via SQLAlchemy's ``postgresql+psycopg2`` dialect."""

    @property
    def database_type(self) -> DatabaseType:
        return DatabaseType.POSTGRESQL

    def _build_url(self, config: SQLConnectionConfig) -> URL:
        return URL.create(
            "postgresql+psycopg2",
            username=config.username,
            password=config.password,
            host=config.host,
            port=config.port or _DEFAULT_PORT,
            database=config.database,
        )

    def _connect_args(self, config: SQLConnectionConfig) -> dict[str, Any]:
        """``sslmode``/``connect_timeout`` are standard libpq parameter names psycopg2 forwards as-is."""
        args: dict[str, Any] = {"connect_timeout": int(config.timeout)}
        if config.ssl:
            args["sslmode"] = "require"
        return args
