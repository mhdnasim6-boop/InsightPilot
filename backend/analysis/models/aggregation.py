"""Aggregation engine models: group-by and pivot-style summaries.

Not a field on ``AnalysisResult`` itself — ``AggregationEngine`` is
standalone reusable infrastructure, used internally by ``InsightEngine``
and exposed for future dashboard/report modules to call directly.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AggregationFunction(str, Enum):
    """Supported group/pivot aggregation functions."""

    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    MEDIAN = "median"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class AggregationResult(BaseModel):
    """The result of a single group-by aggregation."""

    group_column: str
    value_column: str | None = None
    aggregation: AggregationFunction
    results: dict[str, Any] = Field(default_factory=dict)


class PivotResult(BaseModel):
    """The result of a pivot-style (index x columns) aggregation."""

    index: str
    columns: str
    values: str
    aggregation: AggregationFunction
    table: dict[str, dict[str, Any]] = Field(default_factory=dict)
