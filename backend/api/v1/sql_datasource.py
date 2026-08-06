"""SQL data source endpoints: connect, browse, preview, and import.

Thin HTTP wrappers over the existing ``SQLDataSourceService`` — no
business logic here. A successful import also registers the resulting
``BusinessDataset`` into the same ``BusinessDatasetStore`` the upload
endpoint uses, so a SQL-imported dataset shows up in the dashboard's
dataset selector exactly like an uploaded CSV does.
"""

from fastapi import APIRouter, Depends

from backend.core.exceptions import ValidationError
from backend.datasource.sql.models.connection_config import SQLConnectionConfig
from backend.datasource.sql.validation.result import ConnectionValidationResult
from backend.dependencies.ingestion import get_business_dataset_store
from backend.dependencies.sql_datasource import get_sql_data_source_service
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.schemas.response import SuccessResponse
from backend.schemas.sql_datasource import (
    SQLImportQueryRequest,
    SQLImportTableRequest,
    SQLPreviewRequest,
    SQLPreviewResponse,
)
from backend.services.sql_data_source_service import SQLDataSourceService

router = APIRouter(prefix="/datasources/sql")


@router.post(
    "/connect",
    response_model=SuccessResponse[ConnectionValidationResult],
    summary="Validate a SQL connection config and test real connectivity",
)
async def connect(
    config: SQLConnectionConfig, service: SQLDataSourceService = Depends(get_sql_data_source_service)
) -> SuccessResponse[ConnectionValidationResult]:
    """Check the config's shape and attempt a real, temporary connection. Never persists anything."""
    result = service.validate_connection(config)
    message = "Connection successful." if result.is_valid else "Connection failed."
    return SuccessResponse.ok(data=result, message=message)


@router.post("/tables", response_model=SuccessResponse[list[str]], summary="List every table in a database")
async def list_tables(
    config: SQLConnectionConfig, service: SQLDataSourceService = Depends(get_sql_data_source_service)
) -> SuccessResponse[list[str]]:
    """Connect, list every visible table, and disconnect."""
    return SuccessResponse.ok(data=service.list_tables(config), message="Tables fetched.")


@router.post(
    "/preview",
    response_model=SuccessResponse[SQLPreviewResponse],
    summary="Preview a table or a custom query",
)
async def preview(
    request: SQLPreviewRequest, service: SQLDataSourceService = Depends(get_sql_data_source_service)
) -> SuccessResponse[SQLPreviewResponse]:
    """Preview rows from exactly one of ``table_name`` or ``query``.

    Raises ``ValidationError`` (422) if neither or both are given.
    """
    if bool(request.table_name) == bool(request.query):
        raise ValidationError("Exactly one of 'table_name' or 'query' must be given.")

    if request.table_name is not None:
        table_preview, metadata = service.preview_table(request.connection, request.table_name, limit=request.limit)
        response = SQLPreviewResponse(preview=table_preview, metadata=metadata)
    else:
        assert request.query is not None  # guaranteed by the exactly-one-of check above
        query_preview = service.preview_query(request.connection, request.query, limit=request.limit)
        response = SQLPreviewResponse(preview=query_preview)

    return SuccessResponse.ok(data=response, message="Preview fetched.")


@router.post(
    "/import/table",
    response_model=SuccessResponse[BusinessDataset],
    summary="Import a whole table as a new BusinessDataset",
)
async def import_table(
    request: SQLImportTableRequest,
    service: SQLDataSourceService = Depends(get_sql_data_source_service),
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
) -> SuccessResponse[BusinessDataset]:
    """Read a full table and ingest it into a ``BusinessDataset``."""
    dataset = service.import_table(request.connection, request.table_name, dataset_name=request.dataset_name)
    dataset_store.put(dataset)
    return SuccessResponse.ok(data=dataset, message=f"Table '{request.table_name}' imported.")


@router.post(
    "/import/query",
    response_model=SuccessResponse[BusinessDataset],
    summary="Import a custom query's result as a new BusinessDataset",
)
async def import_query(
    request: SQLImportQueryRequest,
    service: SQLDataSourceService = Depends(get_sql_data_source_service),
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
) -> SuccessResponse[BusinessDataset]:
    """Run a custom query and ingest its full result into a ``BusinessDataset``."""
    dataset = service.import_query(request.connection, request.query, dataset_name=request.dataset_name)
    dataset_store.put(dataset)
    return SuccessResponse.ok(data=dataset, message=f"Dataset '{request.dataset_name}' imported.")
