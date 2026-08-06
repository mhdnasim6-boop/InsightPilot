"""Supported (and future) data source types.

Only CSV and Excel are implemented (see
``backend.ingestion.registry.loader_registry``); the rest are recognized
concepts with no loader yet, exactly like AI's ``_PLACEHOLDERS`` provider
names in ``backend.ai.providers.factory``.
"""

from enum import Enum


class SourceType(str, Enum):
    """Every data source InsightPilot recognizes, implemented or not."""

    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    POWERPOINT = "powerpoint"
    WORD = "word"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    DUCKDB = "duckdb"
    API = "api"


# File-extension-based source types only — SQLITE/POSTGRESQL/MYSQL/API are
# connection-based (a DSN or URL, not a file extension) and have no entry
# here; they aren't addressable through the extension-keyed LoaderRegistry.
_EXTENSION_SOURCE_TYPES: dict[str, SourceType] = {
    ".csv": SourceType.CSV,
    ".xlsx": SourceType.EXCEL,
    ".xls": SourceType.EXCEL,
    ".pdf": SourceType.PDF,
    ".docx": SourceType.WORD,
    ".pptx": SourceType.POWERPOINT,
}


def source_type_for_extension(extension: str) -> SourceType | None:
    """Map a file extension to its ``SourceType``, or None if unrecognized."""
    return _EXTENSION_SOURCE_TYPES.get(extension.lower())
