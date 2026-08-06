"""MySQL connector, via SQLAlchemy's ``pymysql`` dialect.

``pymysql`` (pure Python) is used instead of ``mysqlclient`` specifically
to avoid a system-level ``libmysqlclient`` build dependency — the same
reasoning that makes ``psycopg2-binary`` (not plain ``psycopg2``) the
right choice for PostgreSQL.
"""

from typing import Any

from sqlalchemy.engine import URL

from backend.datasource.sql.connectors.base import SQLConnector
from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)

_DEFAULT_PORT = 3306


class MySQLConnector(SQLConnector):
    """Connects to MySQL (or MySQL-compatible servers) via SQLAlchemy's ``mysql+pymysql`` dialect."""

    @property
    def database_type(self) -> DatabaseType:
        return DatabaseType.MYSQL

    def _build_url(self, config: SQLConnectionConfig) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=config.username,
            password=config.password,
            host=config.host,
            port=config.port or _DEFAULT_PORT,
            database=config.database,
        )

    def _connect_args(self, config: SQLConnectionConfig) -> dict[str, Any]:
        """``ssl``/``connect_timeout`` are parameter names ``pymysql.connect()`` accepts directly."""
        args: dict[str, Any] = {"connect_timeout": int(config.timeout)}
        if config.ssl:
            args["ssl"] = {}
        return args
