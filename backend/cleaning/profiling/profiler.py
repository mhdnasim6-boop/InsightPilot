"""Builds a DatasetProfile from an already-loaded DataFrame.

Reuses ``MetadataExtractor`` (columns, types, shape, memory, basic
statistics) rather than recomputing those facts, and adds the
profiling-specific views ingestion doesn't need: duplicate-row detection,
numeric/categorical splits, constant and high-cardinality columns.
"""

from typing import Any

import pandas as pd

from backend.cleaning.models.profile import DatasetProfile
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.metadata.result import DatasetMetadataResult
from backend.utils.time import utc_now


class DatasetProfilingService:
    """Computes a full DatasetProfile for a DataFrame. No AI, no recommendations."""

    def __init__(self, extractor: MetadataExtractor, high_cardinality_ratio: float = 0.9) -> None:
        self._extractor = extractor
        self._high_cardinality_ratio = high_cardinality_ratio

    def profile(self, dataframe: pd.DataFrame, dataset_id: str) -> DatasetProfile:
        """Build a full DatasetProfile for the given DataFrame."""
        metadata_result = self._extractor.extract(dataframe)

        numeric_columns = {
            column.name for column in metadata_result.columns if pd.api.types.is_numeric_dtype(dataframe[column.name])
        }

        return DatasetProfile(
            dataset_id=dataset_id,
            generated_at=utc_now(),
            row_count=metadata_result.row_count,
            column_count=metadata_result.column_count,
            memory_usage_bytes=metadata_result.memory_usage_bytes,
            data_types=metadata_result.column_types,
            missing_value_summary=self._missing_value_summary(metadata_result),
            duplicate_summary=self._duplicate_summary(dataframe),
            column_statistics=metadata_result.statistics,
            numeric_summary={
                name: stats for name, stats in metadata_result.statistics.items() if name in numeric_columns
            },
            categorical_summary={
                name: stats for name, stats in metadata_result.statistics.items() if name not in numeric_columns
            },
            constant_columns=sorted(column.name for column in metadata_result.columns if column.unique_count <= 1),
            high_cardinality_columns=sorted(
                column.name
                for column in metadata_result.columns
                if metadata_result.row_count > 0
                and column.unique_count / metadata_result.row_count > self._high_cardinality_ratio
            ),
        )

    def _missing_value_summary(self, metadata_result: DatasetMetadataResult) -> dict[str, Any]:
        missing_by_column = {column.name: column.null_count for column in metadata_result.columns}
        total_missing = sum(missing_by_column.values())
        total_cells = metadata_result.row_count * metadata_result.column_count
        percentage = round((total_missing / total_cells) * 100, 2) if total_cells > 0 else 0.0
        return {
            "total_missing": total_missing,
            "missing_by_column": missing_by_column,
            "missing_percentage": percentage,
        }

    def _duplicate_summary(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        duplicate_row_count = int(dataframe.duplicated().sum())
        row_count = dataframe.shape[0]
        percentage = round((duplicate_row_count / row_count) * 100, 2) if row_count > 0 else 0.0
        return {"duplicate_row_count": duplicate_row_count, "duplicate_percentage": percentage}
