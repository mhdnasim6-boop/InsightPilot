"""SQL connectors: one abstract contract, one concrete class per dialect."""

from backend.datasource.sql.connectors.base import DEFAULT_PREVIEW_LIMIT, SQLConnector
from backend.datasource.sql.connectors.mysql_connector import MySQLConnector
from backend.datasource.sql.connectors.postgres_connector import PostgresConnector
from backend.datasource.sql.connectors.sqlite_connector import SQLiteConnector

__all__ = [
    "DEFAULT_PREVIEW_LIMIT",
    "MySQLConnector",
    "PostgresConnector",
    "SQLConnector",
    "SQLiteConnector",
]
