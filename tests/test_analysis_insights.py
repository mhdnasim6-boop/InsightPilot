"""Tests for InsightEngine: deterministic, rule-based, reproducible insights."""

import pandas as pd

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.models.anomaly import AnomalyAnalysisResult, ColumnAnomalyResult
from backend.analysis.models.correlation import (
    CorrelationAnalysisResult,
    CorrelationPair,
)
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.trend import TrendAnalysisResult, TrendSeriesResult
from backend.cleaning.models.profile import DatasetProfile
from backend.utils.time import utc_now


def _empty_dataset_summary() -> DatasetSummary:
    return DatasetSummary(row_count=0, column_count=0, missing_values=0, memory_usage_bytes=0, duplicate_count=0)


def _empty_profile(**overrides: object) -> DatasetProfile:
    defaults: dict[str, object] = {
        "dataset_id": "d1",
        "generated_at": utc_now(),
        "row_count": 0,
        "column_count": 0,
        "memory_usage_bytes": 0,
    }
    defaults.update(overrides)
    return DatasetProfile(**defaults)  # type: ignore[arg-type]


def _engine() -> InsightEngine:
    return InsightEngine(AggregationEngine())


def test_missing_value_insight_fires_above_threshold() -> None:
    profile = _empty_profile(row_count=100, missing_value_summary={"missing_by_column": {"amount": 42}})

    insights = _engine().generate(
        pd.DataFrame(),
        profile,
        _empty_dataset_summary(),
        TrendAnalysisResult(applicable=False),
        AnomalyAnalysisResult(applicable=False),
        CorrelationAnalysisResult(applicable=False),
    )

    messages = [insight.message for insight in insights if insight.category == "missing_data"]
    assert "Column 'amount' contains 42.0% missing values." in messages


def test_missing_value_insight_does_not_fire_below_threshold() -> None:
    profile = _empty_profile(row_count=100, missing_value_summary={"missing_by_column": {"amount": 5}})

    insights = _engine().generate(
        pd.DataFrame(),
        profile,
        _empty_dataset_summary(),
        TrendAnalysisResult(applicable=False),
        AnomalyAnalysisResult(applicable=False),
        CorrelationAnalysisResult(applicable=False),
    )

    assert not any(insight.category == "missing_data" for insight in insights)


def test_growth_insight_fires_for_increase_and_decrease() -> None:
    trends = TrendAnalysisResult(
        applicable=True,
        series=[
            TrendSeriesResult(column="sales", growth_rate=18.0),
            TrendSeriesResult(column="returns", growth_rate=-12.0),
        ],
    )

    insights = _engine().generate(
        pd.DataFrame(),
        _empty_profile(),
        _empty_dataset_summary(),
        trends,
        AnomalyAnalysisResult(applicable=False),
        CorrelationAnalysisResult(applicable=False),
    )

    messages = {insight.message for insight in insights if insight.category == "trend"}
    assert "'sales' increased by 18.0%." in messages
    assert "'returns' decreased by 12.0%." in messages


def test_concentration_insight_identifies_top_contributor() -> None:
    df = pd.DataFrame({"region": ["East", "East", "West"], "revenue": [800, 100, 100]})
    dataset_summary = DatasetSummary(
        row_count=3,
        column_count=2,
        missing_values=0,
        memory_usage_bytes=0,
        duplicate_count=0,
        numeric_columns=["revenue"],
        categorical_columns=["region"],
    )

    insights = _engine().generate(
        df,
        _empty_profile(),
        dataset_summary,
        TrendAnalysisResult(applicable=False),
        AnomalyAnalysisResult(applicable=False),
        CorrelationAnalysisResult(applicable=False),
    )

    concentration = [insight for insight in insights if insight.category == "concentration"]
    assert len(concentration) == 1
    assert concentration[0].message == "'East' contributes 90.0% of total revenue."


def test_concentration_insight_does_not_fire_below_threshold() -> None:
    df = pd.DataFrame({"region": ["East", "West", "North"], "revenue": [34, 33, 33]})
    dataset_summary = DatasetSummary(
        row_count=3,
        column_count=2,
        missing_values=0,
        memory_usage_bytes=0,
        duplicate_count=0,
        numeric_columns=["revenue"],
        categorical_columns=["region"],
    )

    insights = _engine().generate(
        df,
        _empty_profile(),
        dataset_summary,
        TrendAnalysisResult(applicable=False),
        AnomalyAnalysisResult(applicable=False),
        CorrelationAnalysisResult(applicable=False),
    )

    assert not any(insight.category == "concentration" for insight in insights)


def test_correlation_insight_reports_strong_pairs() -> None:
    correlations = CorrelationAnalysisResult(
        applicable=True,
        strong_positive=[CorrelationPair(column_a="revenue", column_b="cost", pearson=0.95)],
        strong_negative=[CorrelationPair(column_a="price", column_b="units", pearson=-0.9)],
    )

    insights = _engine().generate(
        pd.DataFrame(),
        _empty_profile(),
        _empty_dataset_summary(),
        TrendAnalysisResult(applicable=False),
        AnomalyAnalysisResult(applicable=False),
        correlations,
    )

    messages = {insight.message for insight in insights if insight.category == "correlation"}
    assert "Strong positive relationship between 'revenue' and 'cost' (r=0.95)." in messages
    assert "Strong negative relationship between 'price' and 'units' (r=-0.9)." in messages


def test_anomaly_insight_reports_columns_above_threshold() -> None:
    anomalies = AnomalyAnalysisResult(
        applicable=True,
        columns=[ColumnAnomalyResult(column="amount", iqr_outlier_count=3, iqr_outlier_percentage=12.0)],
    )

    insights = _engine().generate(
        pd.DataFrame(),
        _empty_profile(),
        _empty_dataset_summary(),
        TrendAnalysisResult(applicable=False),
        anomalies,
        CorrelationAnalysisResult(applicable=False),
    )

    messages = [insight.message for insight in insights if insight.category == "anomaly"]
    assert "Column 'amount' has 3 outlier(s) (12.0% of values) detected via IQR." in messages


def test_generate_returns_no_insights_when_nothing_applicable() -> None:
    insights = _engine().generate(
        pd.DataFrame(),
        _empty_profile(),
        _empty_dataset_summary(),
        TrendAnalysisResult(applicable=False),
        AnomalyAnalysisResult(applicable=False),
        CorrelationAnalysisResult(applicable=False),
    )
    assert insights == []
