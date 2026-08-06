"""Computes rolling average, percentage change, running total, and overall
growth rate for every numeric column, ordered by the detected time column.
"""

import pandas as pd

from backend.analysis.models.trend import TrendAnalysisResult, TrendSeriesResult
from backend.analysis.trends.detection import detect_time_column
from backend.ingestion.metadata.json_safe import to_jsonable


class TrendEngine:
    """Detects a time column and computes trend statistics for every numeric column."""

    def __init__(self, window: int = 3) -> None:
        self._window = window

    def analyze(self, dataframe: pd.DataFrame) -> TrendAnalysisResult:
        """Analyze trends in ``dataframe``, or return a Not Applicable result if no time column exists."""
        time_column = detect_time_column(dataframe)
        if time_column is None:
            return TrendAnalysisResult(
                applicable=False,
                reason="No time-like column detected in the dataset.",
            )

        ordered = dataframe.sort_values(by=time_column)
        numeric_columns = ordered.select_dtypes(include="number").columns

        series_results = [self._analyze_column(ordered[column]) for column in numeric_columns]

        return TrendAnalysisResult(
            applicable=True,
            time_column=time_column,
            window=self._window,
            series=series_results,
        )

    def _analyze_column(self, series: pd.Series) -> TrendSeriesResult:
        rolling_average = to_jsonable(series.rolling(window=self._window).mean().tolist())
        percentage_change = to_jsonable((series.pct_change() * 100).tolist())
        running_total = to_jsonable(series.cumsum().tolist())
        growth_rate = self._growth_rate(series)

        return TrendSeriesResult(
            column=str(series.name),
            rolling_average=rolling_average,
            percentage_change=percentage_change,
            running_total=running_total,
            growth_rate=growth_rate,
        )

    def _growth_rate(self, series: pd.Series) -> float | None:
        non_null = series.dropna()
        if non_null.shape[0] < 2:
            return None
        first, last = non_null.iloc[0], non_null.iloc[-1]
        if first == 0:
            return None
        return to_jsonable(round(((last - first) / abs(first)) * 100, 2))
