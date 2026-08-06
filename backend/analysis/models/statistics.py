"""Descriptive statistics — numeric columns only."""

from pydantic import BaseModel, Field


class ColumnStatistics(BaseModel):
    """Full descriptive statistics for one numeric column."""

    column: str
    mean: float | None = None
    median: float | None = None
    mode: list[float] = Field(default_factory=list)
    std: float | None = None
    variance: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    quartiles: dict[str, float | None] = Field(default_factory=dict)
    percentiles: dict[str, float | None] = Field(default_factory=dict)
    distribution_summary: dict[str, float | None] = Field(default_factory=dict)


class DescriptiveStatistics(BaseModel):
    """Descriptive statistics for every numeric column in a dataset."""

    columns: dict[str, ColumnStatistics] = Field(default_factory=dict)
