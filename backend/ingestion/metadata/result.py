"""The result of extracting metadata from a loaded DataFrame."""

from typing import Any

from pydantic import BaseModel, Field

from backend.ingestion.models.column import ColumnMetadata


class DatasetMetadataResult(BaseModel):
    """Everything ``MetadataExtractor.extract()`` computes from a DataFrame.

    ``column_types`` (not ``schema``) is the internal field name here —
    only the public ``BusinessDataset.schema`` uses that exact name, to
    keep the BaseModel-shadowing warning confined to one place.
    """

    columns: list[ColumnMetadata] = Field(default_factory=list)
    column_types: dict[str, str] = Field(default_factory=dict)
    row_count: int
    column_count: int
    memory_usage_bytes: int
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
