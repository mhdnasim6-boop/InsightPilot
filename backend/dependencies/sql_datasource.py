"""SQL data source providers: connector registry, service.

There is no separate provider for ``SQLTableMetadataExtractor`` — each
connector constructs its own default instance (it's stateless and cheap),
the same way the ingestion layer's loaders don't take an injected
``MetadataExtractor`` either.
"""

from functools import lru_cache

from fastapi import Depends

from backend.datasource.sql.registry.connector_registry import ConnectorRegistry
from backend.dependencies.ingestion import get_ingestion_service
from backend.services.ingestion_service import IngestionService
from backend.services.sql_data_source_service import SQLDataSourceService


@lru_cache
def get_connector_registry() -> ConnectorRegistry:
    """Return the process-wide ConnectorRegistry singleton (stateless, safe to share)."""
    return ConnectorRegistry()


def get_sql_data_source_service(
    connector_registry: ConnectorRegistry = Depends(get_connector_registry),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> SQLDataSourceService:
    """Provide the SQLDataSourceService — the only object that should be used for SQL connectivity."""
    return SQLDataSourceService(connector_registry, ingestion_service)
