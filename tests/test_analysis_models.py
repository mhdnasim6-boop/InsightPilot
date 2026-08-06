"""Tests for analysis models: shapes, defaults, and the central AnalysisResult."""

from backend.analysis.models.aggregation import (
    AggregationFunction,
    AggregationResult,
    PivotResult,
)
from backend.analysis.models.anomaly import AnomalyAnalysisResult, ColumnAnomalyResult
from backend.analysis.models.correlation import CorrelationAnalysisResult
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.insight import Insight
from backend.analysis.models.kpi import KPIDefinition, KPIResult, KPIType
from backend.analysis.models.result import AnalysisResult
from backend.analysis.models.statistics import ColumnStatistics, DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult
from backend.utils.time import utc_now


def test_dataset_summary_defaults() -> None:
    summary = DatasetSummary(row_count=10, column_count=2, missing_values=0, memory_usage_bytes=100, duplicate_count=0)
    assert summary.numeric_columns == []
    assert summary.categorical_columns == []
    assert summary.data_types == {}


def test_column_statistics_defaults() -> None:
    stats = ColumnStatistics(column="a")
    assert stats.mode == []
    assert stats.quartiles == {}
    assert stats.percentiles == {}
    assert stats.distribution_summary == {}


def test_descriptive_statistics_defaults() -> None:
    assert DescriptiveStatistics().columns == {}


def test_kpi_definition_and_result_defaults() -> None:
    definition = KPIDefinition(name="Record Count", kpi_type=KPIType.RECORD_COUNT)
    assert definition.column is None
    assert definition.params == {}

    result = KPIResult(name="Record Count", kpi_type=KPIType.RECORD_COUNT, value=10)
    assert result.column is None


def test_trend_analysis_result_defaults_to_applicable() -> None:
    result = TrendAnalysisResult()
    assert result.applicable is True
    assert result.reason is None
    assert result.series == []


def test_trend_analysis_result_not_applicable() -> None:
    result = TrendAnalysisResult(applicable=False, reason="No time-like column detected in the dataset.")
    assert result.applicable is False
    assert result.reason is not None


def test_correlation_analysis_result_not_applicable() -> None:
    result = CorrelationAnalysisResult(applicable=False, reason="Fewer than two numeric columns.")
    assert result.strong_positive == []
    assert result.strong_negative == []


def test_anomaly_analysis_result_isolation_forest_is_an_explicit_placeholder() -> None:
    result = AnomalyAnalysisResult(applicable=True)
    assert result.isolation_forest.implemented is False
    assert "placeholder" in result.isolation_forest.note.lower()


def test_column_anomaly_result_defaults() -> None:
    result = ColumnAnomalyResult(column="a")
    assert result.zscore_outlier_count == 0
    assert result.iqr_outlier_indices == []


def test_insight_defaults() -> None:
    insight = Insight(category="trend", message="'sales' increased by 18%.")
    assert insight.metric is None
    assert insight.supporting_data == {}


def test_aggregation_result_shape() -> None:
    result = AggregationResult(
        group_column="region", value_column="revenue", aggregation=AggregationFunction.SUM, results={"East": 100.0}
    )
    assert result.results["East"] == 100.0


def test_pivot_result_shape() -> None:
    result = PivotResult(
        index="region",
        columns="category",
        values="revenue",
        aggregation=AggregationFunction.SUM,
        table={"East": {"a": 10.0}},
    )
    assert result.table["East"]["a"] == 10.0


def test_analysis_result_bundles_every_section() -> None:
    now = utc_now()
    result = AnalysisResult(
        analysis_id="a1",
        dataset_id="d1",
        analysis_timestamp=now,
        dataset_summary=DatasetSummary(
            row_count=1, column_count=1, missing_values=0, memory_usage_bytes=1, duplicate_count=0
        ),
        descriptive_statistics=DescriptiveStatistics(),
        trends=TrendAnalysisResult(applicable=False, reason="No time-like column detected in the dataset."),
        anomalies=AnomalyAnalysisResult(applicable=False, reason="No numeric columns available."),
        correlations=CorrelationAnalysisResult(applicable=False, reason="Fewer than two numeric columns."),
        execution_time=0.01,
    )
    assert result.kpis == []
    assert result.insights == []
    assert result.warnings == []
    assert result.metadata == {}
