"""Computes full descriptive statistics for every numeric column."""

import pandas as pd

from backend.analysis.models.statistics import ColumnStatistics, DescriptiveStatistics
from backend.ingestion.metadata.json_safe import to_jsonable


class DescriptiveStatisticsEngine:
    """Computes mean/median/mode/std/variance/min/max/quartiles/percentiles/distribution per numeric column."""

    def compute(self, dataframe: pd.DataFrame) -> DescriptiveStatistics:
        """Compute descriptive statistics for every numeric column in ``dataframe``."""
        numeric_columns = dataframe.select_dtypes(include="number").columns
        columns = {name: self._compute_column(dataframe[name]) for name in numeric_columns}
        return DescriptiveStatistics(columns=columns)

    def _compute_column(self, series: pd.Series) -> ColumnStatistics:
        non_null = series.dropna()
        mode_values = to_jsonable(non_null.mode().tolist()) if not non_null.empty else []

        quartiles = non_null.quantile([0.25, 0.5, 0.75]) if not non_null.empty else pd.Series(dtype=float)
        percentiles = non_null.quantile([0.05, 0.1, 0.9, 0.95]) if not non_null.empty else pd.Series(dtype=float)

        return ColumnStatistics(
            column=str(series.name),
            mean=to_jsonable(series.mean()),
            median=to_jsonable(series.median()),
            mode=mode_values,
            std=to_jsonable(series.std()),
            variance=to_jsonable(series.var()),
            minimum=to_jsonable(series.min()),
            maximum=to_jsonable(series.max()),
            quartiles={
                "q1": to_jsonable(quartiles.get(0.25)),
                "q2": to_jsonable(quartiles.get(0.5)),
                "q3": to_jsonable(quartiles.get(0.75)),
            },
            percentiles={
                "p5": to_jsonable(percentiles.get(0.05)),
                "p10": to_jsonable(percentiles.get(0.1)),
                "p90": to_jsonable(percentiles.get(0.9)),
                "p95": to_jsonable(percentiles.get(0.95)),
            },
            distribution_summary={
                "skewness": to_jsonable(series.skew()),
                "kurtosis": to_jsonable(series.kurt()),
            },
        )
