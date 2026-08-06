"""SQL connectivity's own data shapes — never a DataFrame, never raw rows beyond a bounded preview."""

from backend.datasource.sql.models.connection_config import (
    DatabaseType,
    SQLConnectionConfig,
    source_type_for_database,
)
from backend.datasource.sql.models.table_metadata import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableMetadata,
    TablePreview,
)

__all__ = [
    "ColumnInfo",
    "DatabaseType",
    "ForeignKeyInfo",
    "IndexInfo",
    "SQLConnectionConfig",
    "TableMetadata",
    "TablePreview",
    "source_type_for_database",
]
