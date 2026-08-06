"""Structural metadata about one table, and a small data preview.

Extracted purely from a database's own catalog/information schema (via
``sqlalchemy.inspect()``) — never inferred or guessed, mirroring
``backend.ingestion.models.column.ColumnMetadata``'s "facts, never
judgment" stance for file-based sources.
"""

from typing import Any

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """One column's structural facts, as the database reports them."""

    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    default: str | None = None


class ForeignKeyInfo(BaseModel):
    """One foreign key constraint from this table to another."""

    constrained_columns: list[str] = Field(default_factory=list)
    referred_table: str
    referred_columns: list[str] = Field(default_factory=list)


class IndexInfo(BaseModel):
    """One index defined on this table."""

    name: str | None = None
    column_names: list[str] = Field(default_factory=list)
    unique: bool = False


class TableMetadata(BaseModel):
    """Everything describing one table's structure and rough scale."""

    table_name: str
    columns: list[ColumnInfo] = Field(default_factory=list)
    primary_key_columns: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)
    indexes: list[IndexInfo] = Field(default_factory=list)
    row_count: int
    estimated_size_bytes: int


class TablePreview(BaseModel):
    """A small, bounded sample of rows — for browsing, never for analysis."""

    table_name: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count_previewed: int
