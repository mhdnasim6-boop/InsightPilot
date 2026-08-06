"""Descriptive facts about a DataFrame's shape, types, missing values,
duplicates, and column-level statistics. No recommendations — a future
Analysis agent decides what these facts mean.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetProfile(BaseModel):
    """A structural and statistical snapshot of a DataFrame at one point in time."""

    dataset_id: str
    generated_at: datetime
    row_count: int
    column_count: int
    memory_usage_bytes: int
    data_types: dict[str, str] = Field(default_factory=dict)
    missing_value_summary: dict[str, Any] = Field(default_factory=dict)
    duplicate_summary: dict[str, Any] = Field(default_factory=dict)
    column_statistics: dict[str, Any] = Field(default_factory=dict)
    categorical_summary: dict[str, Any] = Field(default_factory=dict)
    numeric_summary: dict[str, Any] = Field(default_factory=dict)
    constant_columns: list[str] = Field(default_factory=list)
    high_cardinality_columns: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
