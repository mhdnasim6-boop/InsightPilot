"""Generates rule-based insights from already-computed analysis sections.

Every rule is a fixed, deterministic threshold check over data other
engines already produced (or, for "concentration" insights, over a
group-by computed via the reusable ``AggregationEngine``) — nothing here
calls an LLM or makes a judgment call an auditor couldn't reproduce by
hand.
"""

import pandas as pd

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.models.aggregation import AggregationFunction
from backend.analysis.models.anomaly import AnomalyAnalysisResult
from backend.analysis.models.correlation import CorrelationAnalysisResult
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.insight import Insight
from backend.analysis.models.trend import TrendAnalysisResult
from backend.cleaning.models.profile import DatasetProfile


class InsightEngine:
    """Turns already-computed analysis sections into deterministic, reproducible insights."""

    def __init__(
        self,
        aggregation_engine: AggregationEngine,
        missing_value_threshold: float = 20.0,
        growth_rate_threshold: float = 5.0,
        concentration_threshold: float = 50.0,
        anomaly_percentage_threshold: float = 5.0,
        max_group_cardinality: int = 20,
    ) -> None:
        self._aggregation_engine = aggregation_engine
        self._missing_value_threshold = missing_value_threshold
        self._growth_rate_threshold = growth_rate_threshold
        self._concentration_threshold = concentration_threshold
        self._anomaly_percentage_threshold = anomaly_percentage_threshold
        self._max_group_cardinality = max_group_cardinality

    def generate(
        self,
        dataframe: pd.DataFrame,
        profile: DatasetProfile,
        dataset_summary: DatasetSummary,
        trends: TrendAnalysisResult,
        anomalies: AnomalyAnalysisResult,
        correlations: CorrelationAnalysisResult,
    ) -> list[Insight]:
        """Generate every rule-based insight that fires for this dataset."""
        return [
            *self._missing_value_insights(profile),
            *self._growth_insights(trends),
            *self._concentration_insights(dataframe, dataset_summary),
            *self._correlation_insights(correlations),
            *self._anomaly_insights(anomalies),
        ]

    def _missing_value_insights(self, profile: DatasetProfile) -> list[Insight]:
        if profile.row_count == 0:
            return []
        insights = []
        for column, missing_count in profile.missing_value_summary.get("missing_by_column", {}).items():
            percentage = round((missing_count / profile.row_count) * 100, 2)
            if percentage >= self._missing_value_threshold:
                insights.append(
                    Insight(
                        category="missing_data",
                        message=f"Column '{column}' contains {percentage}% missing values.",
                        metric=column,
                        value=percentage,
                    )
                )
        return insights

    def _growth_insights(self, trends: TrendAnalysisResult) -> list[Insight]:
        if not trends.applicable:
            return []
        insights = []
        for series in trends.series:
            if series.growth_rate is None or abs(series.growth_rate) < self._growth_rate_threshold:
                continue
            direction = "increased" if series.growth_rate > 0 else "decreased"
            insights.append(
                Insight(
                    category="trend",
                    message=f"'{series.column}' {direction} by {abs(series.growth_rate)}%.",
                    metric=series.column,
                    value=series.growth_rate,
                )
            )
        return insights

    def _concentration_insights(self, dataframe: pd.DataFrame, dataset_summary: DatasetSummary) -> list[Insight]:
        candidates = [
            column
            for column in dataset_summary.categorical_columns
            if column in dataframe.columns and 1 < dataframe[column].nunique() <= self._max_group_cardinality
        ]
        if not candidates or not dataset_summary.numeric_columns:
            return []

        group_column = min(candidates, key=lambda column: dataframe[column].nunique())
        insights = []
        for value_column in dataset_summary.numeric_columns:
            result = self._aggregation_engine.group_by(dataframe, group_column, value_column, AggregationFunction.SUM)
            numeric_values = {key: value for key, value in result.results.items() if isinstance(value, int | float)}
            total = sum(numeric_values.values())
            if total == 0 or not numeric_values:
                continue

            top_group, top_value = max(numeric_values.items(), key=lambda pair: pair[1])
            share = round((top_value / total) * 100, 2)
            if share >= self._concentration_threshold:
                insights.append(
                    Insight(
                        category="concentration",
                        message=f"'{top_group}' contributes {share}% of total {value_column}.",
                        metric=value_column,
                        value=share,
                        supporting_data={"group_column": group_column, "group": top_group, "total": total},
                    )
                )
        return insights

    def _correlation_insights(self, correlations: CorrelationAnalysisResult) -> list[Insight]:
        if not correlations.applicable:
            return []
        insights = []
        for pair in correlations.strong_positive:
            insights.append(
                Insight(
                    category="correlation",
                    message=f"Strong positive relationship between '{pair.column_a}' and '{pair.column_b}' (r={pair.pearson}).",
                    metric=f"{pair.column_a}:{pair.column_b}",
                    value=pair.pearson,
                )
            )
        for pair in correlations.strong_negative:
            insights.append(
                Insight(
                    category="correlation",
                    message=f"Strong negative relationship between '{pair.column_a}' and '{pair.column_b}' (r={pair.pearson}).",
                    metric=f"{pair.column_a}:{pair.column_b}",
                    value=pair.pearson,
                )
            )
        return insights

    def _anomaly_insights(self, anomalies: AnomalyAnalysisResult) -> list[Insight]:
        if not anomalies.applicable:
            return []
        insights = []
        for column_result in anomalies.columns:
            if column_result.iqr_outlier_percentage >= self._anomaly_percentage_threshold:
                insights.append(
                    Insight(
                        category="anomaly",
                        message=(
                            f"Column '{column_result.column}' has {column_result.iqr_outlier_count} outlier(s) "
                            f"({column_result.iqr_outlier_percentage}% of values) detected via IQR."
                        ),
                        metric=column_result.column,
                        value=column_result.iqr_outlier_percentage,
                    )
                )
        return insights
