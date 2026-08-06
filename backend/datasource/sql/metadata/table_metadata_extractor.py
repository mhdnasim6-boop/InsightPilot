"""Extracts ``TableMetadata`` from a live SQLAlchemy ``Engine``.

One implementation shared by every connector (SQLite, Postgres, MySQL,
and any future dialect) — ``sqlalchemy.inspect()`` normalizes catalog
introspection across dialects, so there is nothing dialect-specific left
to duplicate here.
"""

import pandas as pd
from sqlalchemy import Engine, MetaData, Table, func, inspect, select

from backend.datasource.sql.models.table_metadata import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableMetadata,
)

_SIZE_ESTIMATE_SAMPLE_ROWS = 50


class SQLTableMetadataExtractor:
    """Computes a ``TableMetadata`` for one table on an already-connected engine."""

    def extract(self, engine: Engine, table_name: str) -> TableMetadata:
        """Extract columns, keys, indexes, row count, and an estimated size for ``table_name``."""
        inspector = inspect(engine)

        primary_key_columns = list(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])

        columns = [
            ColumnInfo(
                name=str(column["name"]),
                data_type=str(column["type"]),
                nullable=bool(column["nullable"]),
                primary_key=str(column["name"]) in primary_key_columns,
                default=str(column["default"]) if column["default"] is not None else None,
            )
            for column in inspector.get_columns(table_name)
        ]

        foreign_keys = [
            ForeignKeyInfo(
                constrained_columns=list(fk["constrained_columns"]),
                referred_table=str(fk["referred_table"]),
                referred_columns=list(fk["referred_columns"]),
            )
            for fk in inspector.get_foreign_keys(table_name)
        ]

        indexes = [
            IndexInfo(
                name=index.get("name"),
                column_names=[name for name in index["column_names"] if name is not None],
                unique=bool(index.get("unique", False)),
            )
            for index in inspector.get_indexes(table_name)
        ]

        metadata_obj = MetaData()
        table = Table(table_name, metadata_obj, autoload_with=engine)

        with engine.connect() as connection:
            row_count = connection.execute(select(func.count()).select_from(table)).scalar() or 0
            sample = pd.read_sql_query(select(table).limit(_SIZE_ESTIMATE_SAMPLE_ROWS), connection)

        estimated_size_bytes = _estimate_size_bytes(sample, row_count)

        return TableMetadata(
            table_name=table_name,
            columns=columns,
            primary_key_columns=primary_key_columns,
            foreign_keys=foreign_keys,
            indexes=indexes,
            row_count=int(row_count),
            estimated_size_bytes=estimated_size_bytes,
        )


def _estimate_size_bytes(sample: pd.DataFrame, row_count: int) -> int:
    """Extrapolate total table size from a small sample's in-memory footprint.

    Not exact — an estimate, as the field name says. Portable across every
    dialect without a dialect-specific catalog-stats query (Postgres'
    ``pg_total_relation_size``, MySQL's ``information_schema`` columns,
    SQLite's absence of any such thing).
    """
    if sample.empty or row_count == 0:
        return 0
    bytes_per_row = sample.memory_usage(deep=True).sum() / len(sample)
    return int(bytes_per_row * row_count)
