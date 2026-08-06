"""The analysis layer's own dataset summary — a curated adapter over
``DatasetProfile``, not a recomputation of it.
"""

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    """A curated, analysis-facing summary of the dataset being analyzed."""

    row_count: int
    column_count: int
    numeric_columns: list[str] = Field(default_factory=list)
    categorical_columns: list[str] = Field(default_factory=list)
    missing_values: int
    memory_usage_bytes: int
    duplicate_count: int
    data_types: dict[str, str] = Field(default_factory=dict)
