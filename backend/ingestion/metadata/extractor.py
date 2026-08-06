"""Extracts columns, types, shape, missing values, memory usage, and basic
statistics from an already-loaded DataFrame. No cleaning, no judgment.
"""

import pandas as pd

from backend.ingestion.metadata.json_safe import to_jsonable
from backend.ingestion.metadata.result import DatasetMetadataResult
from backend.ingestion.models.column import ColumnMetadata


class MetadataExtractor:
    """Computes a ``DatasetMetadataResult`` from a loaded DataFrame."""

    def extract(self, dataframe: pd.DataFrame, sample_size: int = 5) -> DatasetMetadataResult:
        """Extract column-level and dataset-level descriptive metadata."""
        columns = [
            ColumnMetadata(
                name=str(name),
                dtype=str(dataframe[name].dtype),
                non_null_count=int(dataframe[name].notna().sum()),
                null_count=int(dataframe[name].isna().sum()),
                unique_count=int(dataframe[name].nunique()),
            )
            for name in dataframe.columns
        ]
        column_types = {column.name: column.dtype for column in columns}

        sample_rows: list[dict[str, object]] = [
            {str(key): value for key, value in record.items()}
            for record in dataframe.head(sample_size).to_dict(orient="records")
        ]
        statistics = dataframe.describe(include="all").to_dict()

        return DatasetMetadataResult(
            columns=columns,
            column_types=column_types,
            row_count=int(dataframe.shape[0]),
            column_count=int(dataframe.shape[1]),
            memory_usage_bytes=int(dataframe.memory_usage(deep=True).sum()),
            sample_rows=to_jsonable(sample_rows),
            statistics=to_jsonable(statistics),
        )
