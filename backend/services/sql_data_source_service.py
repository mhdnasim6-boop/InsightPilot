"""SQL data source entry point.

The only object anything (a router, a future SQL-aware agent, a test)
should use to work with a relational database — never a
``SQLConnector``, the ``ConnectorRegistry``, or SQLAlchemy directly.
Every method connects, does exactly one thing, and disconnects; nothing
here holds a connection open between calls, and nothing here returns a
live connection or a raw credential to its caller.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pandas as pd

from backend.datasource.sql.connectors.base import DEFAULT_PREVIEW_LIMIT, SQLConnector
from backend.datasource.sql.models.connection_config import (
    SQLConnectionConfig,
    source_type_for_database,
)
from backend.datasource.sql.models.table_metadata import TableMetadata, TablePreview
from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.datasource.sql.validation.result import ConnectionValidationResult
from backend.ingestion.metadata.json_safe import to_jsonable
from backend.ingestion.models.dataset import BusinessDataset
from backend.services.ingestion_service import IngestionService


class SQLDataSourceService:
    """Validates connections, browses tables, and imports SQL data as a ``BusinessDataset``."""

    def __init__(self, connector_registry: ConnectorRegistry, ingestion_service: IngestionService) -> None:
        self._connector_registry = connector_registry
        self._ingestion_service = ingestion_service

    def validate_connection(self, config: SQLConnectionConfig) -> ConnectionValidationResult:
        """Check the config's shape and, if that passes, attempt a real, temporary connection."""
        connector = self._connector_registry.get_connector(config.database_type)
        return connector.validate(config)

    def list_tables(self, config: SQLConnectionConfig) -> list[str]:
        """List every table visible to this connection."""
        with self._connected(config) as connector:
            return connector.list_tables()

    def describe_table(self, config: SQLConnectionConfig, table_name: str) -> TableMetadata:
        """Describe one table's columns, keys, indexes, row count, and estimated size."""
        with self._connected(config) as connector:
            return connector.describe_table(table_name)

    def preview_table(
        self, config: SQLConnectionConfig, table_name: str, limit: int = DEFAULT_PREVIEW_LIMIT
    ) -> tuple[TablePreview, TableMetadata]:
        """Fetch a bounded row sample and the full structural metadata for one table."""
        with self._connected(config) as connector:
            return connector.preview(table_name, limit=limit), connector.describe_table(table_name)

    def preview_query(
        self, config: SQLConnectionConfig, query: str, limit: int = DEFAULT_PREVIEW_LIMIT
    ) -> TablePreview:
        """Run a custom query and return up to ``limit`` of its rows.

        The full result is fetched, then truncated on the Python side —
        simpler and fully dialect-agnostic compared to wrapping arbitrary
        SQL in a dialect-specific ``LIMIT`` subquery, at the cost of not
        pushing the limit down to the database. Acceptable for a
        lightweight preview; :meth:`import_query` is what runs a query
        for its full result.
        """
        dataframe = self._execute(config, query)
        truncated = dataframe.head(limit)
        return TablePreview(
            columns=[str(column) for column in truncated.columns],
            rows=to_jsonable(truncated.to_dict(orient="records")),
            row_count_previewed=len(truncated),
        )

    def import_table(
        self, config: SQLConnectionConfig, table_name: str, dataset_name: str | None = None
    ) -> BusinessDataset:
        """Read a full table and wrap it into a ``BusinessDataset``."""
        with self._connected(config) as connector:
            dataframe = connector.read_table(table_name)

        return self._ingest(dataframe, config, dataset_name or table_name, source_descriptor=table_name)

    def import_query(self, config: SQLConnectionConfig, query: str, dataset_name: str) -> BusinessDataset:
        """Run a custom query and wrap its full result into a ``BusinessDataset``."""
        dataframe = self._execute(config, query)
        return self._ingest(dataframe, config, dataset_name, source_descriptor=query)

    # -- Internals ------------------------------------------------------------

    def _execute(self, config: SQLConnectionConfig, query: str) -> pd.DataFrame:
        with self._connected(config) as connector:
            return connector.execute_query(query)

    def _ingest(
        self, dataframe: pd.DataFrame, config: SQLConnectionConfig, dataset_name: str, source_descriptor: str
    ) -> BusinessDataset:
        location = config.host or config.database
        return self._ingestion_service.ingest_dataframe(
            dataframe,
            dataset_name=dataset_name,
            source_type=source_type_for_database(config.database_type),
            source_location=f"{config.database_type.value}://{location}/{source_descriptor}",
            metadata=self._connection_metadata(config, source_descriptor),
        )

    def _connection_metadata(self, config: SQLConnectionConfig, source_descriptor: str) -> dict[str, Any]:
        """Provenance recorded on the resulting ``BusinessDataset`` — never a credential."""
        return {
            "sql": {
                "database_type": config.database_type.value,
                "host": config.host,
                "database": config.database,
                "source": source_descriptor,
            }
        }

    @contextmanager
    def _connected(self, config: SQLConnectionConfig) -> Iterator[SQLConnector]:
        """Connect for the duration of one operation, always disconnecting afterward."""
        connector = self._connector_registry.get_connector(config.database_type)
        connector.connect(config)
        try:
            yield connector
        finally:
            connector.disconnect()
