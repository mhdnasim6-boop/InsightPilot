"""Abstract SQL connector: the contract every dialect (implemented or future) satisfies.

Only ``database_type``, ``_build_url()``, and ``_connect_args()`` are
abstract — every other method is concrete here, because
``sqlalchemy.inspect()``/``pandas.read_sql_query()`` behave identically
regardless of dialect once a working ``Engine`` exists. That is what
keeps ``SQLiteConnector``/``PostgresConnector``/``MySQLConnector`` each a
handful of lines instead of three parallel copies of the same query and
introspection logic.
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
from pandas.errors import DatabaseError as PandasDatabaseError
from sqlalchemy import Engine, MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from backend.datasource.sql.exceptions.errors import (
    ConnectionFailedError,
    QueryExecutionError,
    TableNotFoundError,
)
from backend.datasource.sql.metadata.table_metadata_extractor import (
    SQLTableMetadataExtractor,
)
from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
)
from backend.datasource.sql.models.table_metadata import TableMetadata, TablePreview
from backend.datasource.sql.validation.checks import check_connection_config
from backend.datasource.sql.validation.result import ConnectionValidationResult
from backend.ingestion.metadata.json_safe import to_jsonable

DEFAULT_PREVIEW_LIMIT = 10


class SQLConnector(ABC):
    """Contract every SQL connector must satisfy: connect, browse, query, disconnect."""

    def __init__(self, metadata_extractor: SQLTableMetadataExtractor | None = None) -> None:
        self._engine: Engine | None = None
        self._metadata_extractor = metadata_extractor or SQLTableMetadataExtractor()

    @property
    @abstractmethod
    def database_type(self) -> DatabaseType:
        """The ``DatabaseType`` this connector implements."""

    @abstractmethod
    def _build_url(self, config: SQLConnectionConfig) -> URL:
        """Build the dialect-specific SQLAlchemy connection URL."""

    def _connect_args(self, config: SQLConnectionConfig) -> dict[str, Any]:
        """Dialect-specific ``connect_args`` (SSL/timeout parameter names). Default: none."""
        return {}

    # -- Lifecycle ------------------------------------------------------------

    def connect(self, config: SQLConnectionConfig) -> None:
        """Establish and eagerly test a connection. Raises ``ConnectionFailedError`` on failure."""
        try:
            engine = self._create_and_test_engine(config)
        except SQLAlchemyError as exc:
            raise ConnectionFailedError(f"Could not connect to {self.database_type.value} database: {exc}") from exc
        self._engine = engine

    def disconnect(self) -> None:
        """Dispose the engine and release any pooled connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    # -- Browsing ---------------------------------------------------------------

    def list_tables(self) -> list[str]:
        """List every table visible to this connection, alphabetically."""
        return sorted(inspect(self._require_engine()).get_table_names())

    def describe_table(self, table_name: str) -> TableMetadata:
        """Describe one table's structure and rough scale. Raises ``TableNotFoundError`` if unknown."""
        engine = self._require_engine()
        self._require_table_exists(engine, table_name)
        return self._metadata_extractor.extract(engine, table_name)

    def preview(self, table_name: str, limit: int = DEFAULT_PREVIEW_LIMIT) -> TablePreview:
        """Fetch up to ``limit`` rows from ``table_name``. Raises ``TableNotFoundError`` if unknown."""
        dataframe = self._read_table(table_name, limit=limit)
        return TablePreview(
            table_name=table_name,
            columns=[str(column) for column in dataframe.columns],
            rows=to_jsonable(dataframe.to_dict(orient="records")),
            row_count_previewed=len(dataframe),
        )

    def read_table(self, table_name: str) -> pd.DataFrame:
        """Fetch a table's full contents as a DataFrame. Raises ``TableNotFoundError`` if unknown.

        Not part of the required connector interface, but a natural,
        shared extension of it: the same safe, reflected-table read
        :meth:`preview` uses, just without a row limit — this is what
        importing a whole table needs, and keeping identifier quoting in
        one place (here) is safer than a caller hand-building
        ``f"SELECT * FROM {table_name}"``.
        """
        return self._read_table(table_name, limit=None)

    def execute_query(self, query: str) -> pd.DataFrame:
        """Run a raw SQL query and return its full result as a DataFrame."""
        engine = self._require_engine()
        try:
            with engine.connect() as connection:
                return pd.read_sql_query(text(query), connection)
        except (SQLAlchemyError, PandasDatabaseError) as exc:
            # pandas.read_sql_query() re-wraps a driver/SQLAlchemy failure into its
            # own pandas.errors.DatabaseError (an OSError subclass, unrelated to
            # SQLAlchemyError) — both must be caught to convert every query
            # failure into one consistent exception type.
            raise QueryExecutionError(f"Query execution failed: {exc}") from exc

    def validate(self, config: SQLConnectionConfig) -> ConnectionValidationResult:
        """Check the config's shape, then (if that passes) attempt a real, temporary connection."""
        issues = check_connection_config(config)
        if issues:
            return ConnectionValidationResult(
                is_valid=False,
                database_type=config.database_type,
                message="Invalid connection configuration.",
                issues=issues,
            )
        try:
            engine = self._create_and_test_engine(config)
            engine.dispose()
        except SQLAlchemyError as exc:
            return ConnectionValidationResult(
                is_valid=False, database_type=config.database_type, message=f"Connection failed: {exc}"
            )
        return ConnectionValidationResult(
            is_valid=True, database_type=config.database_type, message="Connection successful."
        )

    # -- Internals --------------------------------------------------------------

    def _create_and_test_engine(self, config: SQLConnectionConfig) -> Engine:
        """Build an engine and eagerly test it with ``SELECT 1``. Propagates ``SQLAlchemyError`` uncaught."""
        engine = create_engine(self._build_url(config), connect_args=self._connect_args(config))
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return engine

    def _read_table(self, table_name: str, limit: int | None) -> pd.DataFrame:
        engine = self._require_engine()
        self._require_table_exists(engine, table_name)
        table = Table(table_name, MetaData(), autoload_with=engine)
        statement = select(table).limit(limit) if limit is not None else select(table)
        try:
            with engine.connect() as connection:
                return pd.read_sql_query(statement, connection)
        except (SQLAlchemyError, PandasDatabaseError) as exc:
            raise QueryExecutionError(f"Failed to read table '{table_name}': {exc}") from exc

    def _require_engine(self) -> Engine:
        if self._engine is None:
            raise ConnectionFailedError("Not connected — call connect() first.")
        return self._engine

    def _require_table_exists(self, engine: Engine, table_name: str) -> None:
        if table_name not in inspect(engine).get_table_names():
            raise TableNotFoundError(f"Table '{table_name}' was not found.")
