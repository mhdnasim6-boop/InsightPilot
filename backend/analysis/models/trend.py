"""Trend analysis results.

"Rolling average" and "moving average" are the same computation (a
windowed mean) — represented once as ``rolling_average`` rather than
duplicated under two names.
"""

from pydantic import Field

from backend.analysis.models.common import AnalysisSectionResult


class TrendSeriesResult(AnalysisSectionResult):
    """Trend statistics for one numeric column, ordered by the detected time column."""

    column: str
    rolling_average: list[float | None] = Field(default_factory=list)
    percentage_change: list[float | None] = Field(default_factory=list)
    running_total: list[float | None] = Field(default_factory=list)
    growth_rate: float | None = None


class TrendAnalysisResult(AnalysisSectionResult):
    """Trend analysis for the whole dataset.

    ``applicable`` is False (with ``reason`` set) when no time-like column
    is detected — a structured "Not Applicable" result rather than an
    error or an empty-but-ambiguous success.
    """

    time_column: str | None = None
    window: int = 3
    series: list[TrendSeriesResult] = Field(default_factory=list)
