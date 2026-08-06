"""SQLite connector: the only dialect with no server, host, or credentials."""

from typing import Any

from sqlalchemy.engine import URL

from backend.datasource.sql.connectors.base import SQLConnector
from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)


class SQLiteConnector(SQLConnector):
    """Connects to a SQLite file (or an in-memory database) via SQLAlchemy."""

    @property
    def database_type(self) -> DatabaseType:
        return DatabaseType.SQLITE

    def _build_url(self, config: SQLConnectionConfig) -> URL:
        """``config.database`` is a file path (or ``":memory:"``) — there is no host/port/credentials."""
        return URL.create("sqlite", database=config.database)

    def _connect_args(self, config: SQLConnectionConfig) -> dict[str, Any]:
        """``timeout`` maps to sqlite3's own busy-timeout; SQLite has no SSL concept."""
        return {"timeout": config.timeout}
