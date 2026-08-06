"""Request/response wrapper schemas for the SQL data source endpoints."""

from pydantic import BaseModel, Field

from backend.datasource.sql.models.connection_config import SQLConnectionConfig
from backend.datasource.sql.models.table_metadata import TableMetadata, TablePreview

_DEFAULT_LIMIT = 10
_MAX_LIMIT = 1000


class SQLPreviewRequest(BaseModel):
    """Preview either a table or a custom query — exactly one of the two must be given."""

    connection: SQLConnectionConfig
    table_name: str | None = None
    query: str | None = None
    limit: int = Field(default=_DEFAULT_LIMIT, gt=0, le=_MAX_LIMIT)


class SQLPreviewResponse(BaseModel):
    """A bounded row sample, plus the table's full structure when previewing a named table."""

    preview: TablePreview
    metadata: TableMetadata | None = None


class SQLImportTableRequest(BaseModel):
    """Import a whole table as a new ``BusinessDataset``."""

    connection: SQLConnectionConfig
    table_name: str
    dataset_name: str | None = None


class SQLImportQueryRequest(BaseModel):
    """Import a custom query's full result as a new ``BusinessDataset``."""

    connection: SQLConnectionConfig
    query: str
    dataset_name: str
