"""SQL data source exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing.
"""

from backend.core.exceptions import InsightPilotError


class SQLDataSourceError(InsightPilotError):
    """Base class for all SQL data source exceptions."""

    status_code = 500
    error_type = "SQLDataSourceError"


class UnsupportedDatabaseError(SQLDataSourceError):
    """Raised for a database type with no registered (or placeholder) connector."""

    status_code = 400
    error_type = "UnsupportedDatabaseError"


class DatabaseNotImplementedError(SQLDataSourceError):
    """Raised for a recognized database type (e.g. Snowflake) with no connector implementation yet."""

    status_code = 501
    error_type = "DatabaseNotImplementedError"


class ConnectionFailedError(SQLDataSourceError):
    """Raised when a connector cannot establish or validate a connection."""

    status_code = 502
    error_type = "ConnectionFailedError"


class TableNotFoundError(SQLDataSourceError):
    """Raised when a requested table doesn't exist in the connected database."""

    status_code = 404
    error_type = "TableNotFoundError"


class QueryExecutionError(SQLDataSourceError):
    """Raised when a query fails to execute (bad SQL, permissions, ...)."""

    status_code = 422
    error_type = "QueryExecutionError"
