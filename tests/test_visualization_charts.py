"""Tests for every chart generator, using small deterministic datasets."""

from typing import Any

import pandas as pd

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.models.anomaly import AnomalyAnalysisResult
from backend.analysis.models.correlation import (
    CorrelationAnalysisResult,
    CorrelationPair,
)
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.kpi import KPIResult, KPIType
from backend.analysis.models.result import AnalysisResult
from backend.analysis.models.statistics import ColumnStatistics, DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult, TrendSeriesResult
from backend.utils.time import utc_now
from backend.visualization.charts.bar import BarChartGenerator
from backend.visualization.charts.box import BoxPlotGenerator
from backend.visualization.charts.distribution import DistributionPlotGenerator
from backend.visualization.charts.heatmap import (
    CorrelationMatrixGenerator,
    HeatmapGenerator,
)
from backend.visualization.charts.histogram import HistogramGenerator
from backend.visualization.charts.kpi_cards import KPICardGenerator
from backend.visualization.charts.line import LineChartGenerator
from backend.visualization.charts.pie import PieChartGenerator
from backend.visualization.charts.scatter import ScatterPlotGenerator
from backend.visualization.charts.treemap import TreemapPlaceholderGenerator
from backend.visualization.models.chart import ChartType
from backend.visualization.models.context import ChartContext


def _summary(**overrides: Any) -> DatasetSummary:
    defaults: dict[str, Any] = {
        "row_count": 0,
        "column_count": 0,
        "missing_values": 0,
        "memory_usage_bytes": 0,
        "duplicate_count": 0,
    }
    defaults.update(overrides)
    return DatasetSummary(**defaults)


def _analysis_result(**overrides: Any) -> AnalysisResult:
    defaults: dict[str, Any] = {
        "analysis_id": "a1",
        "dataset_id": "d1",
        "analysis_timestamp": utc_now(),
        "dataset_summary": _summary(),
        "descriptive_statistics": DescriptiveStatistics(),
        "trends": TrendAnalysisResult(applicable=False, reason="No time-like column detected."),
        "anomalies": AnomalyAnalysisResult(applicable=False, reason="No numeric columns."),
        "correlations": CorrelationAnalysisResult(applicable=False, reason="Fewer than two numeric columns."),
        "execution_time": 0.01,
    }
    defaults.update(overrides)
    return AnalysisResult(**defaults)


# --- LineChartGenerator ------------------------------------------------


def test_line_chart_not_applicable_without_trends() -> None:
    context = ChartContext(analysis_result=_analysis_result())
    applicable, reason = LineChartGenerator().applicable(context)
    assert applicable is False
    assert reason


def test_line_chart_generates_from_trend_series() -> None:
    trends = TrendAnalysisResult(
        applicable=True,
        time_column="date",
        window=3,
        series=[TrendSeriesResult(column="revenue", rolling_average=[None, None, 100.0], growth_rate=10.0)],
    )
    context = ChartContext(analysis_result=_analysis_result(trends=trends))
    generator = LineChartGenerator()

    assert generator.applicable(context)[0] is True
    spec = generator.generate(context)

    assert spec.chart_type == ChartType.LINE
    assert spec.series[0].y == [None, None, 100.0]
    assert spec.series[0].metadata["growth_rate"] == 10.0


# --- BoxPlotGenerator ---------------------------------------------------


def test_box_plot_not_applicable_without_statistics() -> None:
    context = ChartContext(analysis_result=_analysis_result())
    assert BoxPlotGenerator().applicable(context)[0] is False


def test_box_plot_generates_quartiles_from_descriptive_statistics() -> None:
    stats = DescriptiveStatistics(
        columns={
            "amount": ColumnStatistics(
                column="amount", minimum=1.0, maximum=10.0, quartiles={"q1": 2.0, "q2": 5.0, "q3": 8.0}
            )
        }
    )
    context = ChartContext(analysis_result=_analysis_result(descriptive_statistics=stats))

    spec = BoxPlotGenerator().generate(context)

    assert spec.series[0].metadata["q1"] == 2.0
    assert spec.series[0].metadata["max"] == 10.0


# --- KPICardGenerator -----------------------------------------------------


def test_kpi_cards_not_applicable_without_kpis() -> None:
    context = ChartContext(analysis_result=_analysis_result())
    assert KPICardGenerator().applicable(context)[0] is False


def test_kpi_cards_generates_one_series_per_kpi() -> None:
    kpis = [KPIResult(name="Record Count", kpi_type=KPIType.RECORD_COUNT, value=10)]
    context = ChartContext(analysis_result=_analysis_result(kpis=kpis))

    spec = KPICardGenerator().generate(context)

    assert spec.chart_type == ChartType.KPI_CARD
    assert spec.series[0].name == "Record Count"
    assert spec.series[0].y == [10]
    assert spec.interactive is False


def test_kpi_cards_respects_max_cards() -> None:
    kpis = [KPIResult(name=f"KPI {i}", kpi_type=KPIType.RECORD_COUNT, value=i) for i in range(5)]
    context = ChartContext(analysis_result=_analysis_result(kpis=kpis))

    spec = KPICardGenerator(max_cards=2).generate(context)

    assert len(spec.series) == 2


# --- HeatmapGenerator / CorrelationMatrixGenerator -------------------------


def test_correlation_matrix_not_applicable() -> None:
    context = ChartContext(analysis_result=_analysis_result())
    assert CorrelationMatrixGenerator().applicable(context)[0] is False


def test_correlation_matrix_generates_a_z_matrix() -> None:
    correlations = CorrelationAnalysisResult(
        applicable=True,
        columns=["a", "b"],
        pearson_matrix={"a": {"a": 1.0, "b": 0.5}, "b": {"a": 0.5, "b": 1.0}},
    )
    context = ChartContext(analysis_result=_analysis_result(correlations=correlations))

    spec = CorrelationMatrixGenerator().generate(context)

    assert spec.chart_type == ChartType.CORRELATION_MATRIX
    assert spec.series[0].z == [[1.0, 0.5], [0.5, 1.0]]


def test_heatmap_generator_also_uses_correlation_data() -> None:
    correlations = CorrelationAnalysisResult(applicable=True, columns=["a"], pearson_matrix={"a": {"a": 1.0}})
    context = ChartContext(analysis_result=_analysis_result(correlations=correlations))

    spec = HeatmapGenerator().generate(context)

    assert spec.chart_type == ChartType.HEATMAP


# --- BarChartGenerator / PieChartGenerator (need a DataFrame + AggregationEngine) --


def _category_df() -> pd.DataFrame:
    return pd.DataFrame({"region": ["East", "East", "West", "West"], "amount": [100, 150, 50, 60]})


def _category_summary() -> DatasetSummary:
    return _summary(row_count=4, column_count=2, numeric_columns=["amount"], categorical_columns=["region"])


def test_bar_chart_not_applicable_without_dataframe() -> None:
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=_category_summary()))
    assert BarChartGenerator(AggregationEngine()).applicable(context)[0] is False


def test_bar_chart_generates_grouped_sums() -> None:
    context = ChartContext(
        analysis_result=_analysis_result(dataset_summary=_category_summary()), dataframe=_category_df()
    )

    spec = BarChartGenerator(AggregationEngine()).generate(context)

    assert dict(zip(spec.series[0].x, spec.series[0].y, strict=True)) == {"East": 250, "West": 110}


def test_pie_chart_generates_shares_by_category() -> None:
    context = ChartContext(
        analysis_result=_analysis_result(dataset_summary=_category_summary()), dataframe=_category_df()
    )

    spec = PieChartGenerator(AggregationEngine()).generate(context)

    assert dict(zip(spec.series[0].x, spec.series[0].y, strict=True)) == {"East": 250, "West": 110}


def test_pie_chart_buckets_extra_categories_into_other() -> None:
    df = pd.DataFrame({"region": ["A", "B", "C"], "amount": [10, 20, 30]})
    summary = _summary(row_count=3, column_count=2, numeric_columns=["amount"], categorical_columns=["region"])
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=summary), dataframe=df)

    spec = PieChartGenerator(AggregationEngine(), max_slices=1).generate(context)

    assert spec.series[0].x == ["C", "Other"]
    assert spec.series[0].y == [30, 30]


# --- ScatterPlotGenerator ---------------------------------------------------


def test_scatter_not_applicable_with_fewer_than_two_numeric_columns() -> None:
    summary = _summary(row_count=2, column_count=1, numeric_columns=["a"])
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=summary), dataframe=pd.DataFrame({"a": [1, 2]}))
    assert ScatterPlotGenerator().applicable(context)[0] is False


def test_scatter_generates_xy_pairs() -> None:
    summary = _summary(row_count=4, column_count=2, numeric_columns=["a", "b"])
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8]})
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=summary), dataframe=df)

    spec = ScatterPlotGenerator().generate(context)

    assert spec.series[0].x == [1, 2, 3, 4]
    assert spec.series[0].y == [2, 4, 6, 8]


def test_scatter_prefers_the_strongest_correlated_pair() -> None:
    summary = _summary(row_count=4, column_count=3, numeric_columns=["a", "b", "c"])
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [10, 10, 10, 11], "c": [2, 4, 6, 8]})
    correlations = CorrelationAnalysisResult(
        applicable=True,
        columns=["a", "b", "c"],
        strong_positive=[CorrelationPair(column_a="a", column_b="c", pearson=1.0)],
    )
    context = ChartContext(
        analysis_result=_analysis_result(dataset_summary=summary, correlations=correlations), dataframe=df
    )

    spec = ScatterPlotGenerator().generate(context)

    assert spec.x_axis is not None and spec.x_axis.column == "a"
    assert spec.y_axis is not None and spec.y_axis.column == "c"


# --- HistogramGenerator ------------------------------------------------------


def test_histogram_not_applicable_without_numeric_columns() -> None:
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=_summary()), dataframe=pd.DataFrame())
    assert HistogramGenerator().applicable(context)[0] is False


def test_histogram_generates_binned_counts_summing_to_row_count() -> None:
    summary = _summary(row_count=10, column_count=1, numeric_columns=["amount"])
    df = pd.DataFrame({"amount": list(range(10))})
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=summary), dataframe=df)

    spec = HistogramGenerator(bins=2).generate(context)

    assert len(spec.series[0].x) == 2
    assert sum(spec.series[0].y) == 10


# --- DistributionPlotGenerator ------------------------------------------------


def test_distribution_plot_not_applicable_without_dataframe() -> None:
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=_summary(numeric_columns=["a"])))
    assert DistributionPlotGenerator().applicable(context)[0] is False


def test_distribution_plot_generates_raw_values_and_shape_metadata() -> None:
    stats = DescriptiveStatistics(
        columns={"amount": ColumnStatistics(column="amount", distribution_summary={"skewness": 0.1, "kurtosis": -0.2})}
    )
    summary = _summary(row_count=3, column_count=1, numeric_columns=["amount"])
    df = pd.DataFrame({"amount": [1, 2, 3]})
    context = ChartContext(
        analysis_result=_analysis_result(dataset_summary=summary, descriptive_statistics=stats), dataframe=df
    )

    spec = DistributionPlotGenerator().generate(context)

    assert spec.series[0].x == [1, 2, 3]
    assert spec.series[0].metadata["skewness"] == 0.1


# --- TreemapPlaceholderGenerator ----------------------------------------------


def test_treemap_not_applicable_with_low_cardinality() -> None:
    df = pd.DataFrame({"region": ["East", "West"] * 5})
    summary = _summary(row_count=10, column_count=1, categorical_columns=["region"])
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=summary), dataframe=df)

    assert TreemapPlaceholderGenerator(cardinality_threshold=5).applicable(context)[0] is False


def test_treemap_applicable_with_high_cardinality_and_is_an_explicit_placeholder() -> None:
    df = pd.DataFrame({"customer_id": [f"cust_{i}" for i in range(30)]})
    summary = _summary(row_count=30, column_count=1, categorical_columns=["customer_id"])
    context = ChartContext(analysis_result=_analysis_result(dataset_summary=summary), dataframe=df)
    generator = TreemapPlaceholderGenerator(cardinality_threshold=20)

    assert generator.applicable(context)[0] is True
    spec = generator.generate(context)

    assert spec.chart_type == ChartType.TREEMAP
    assert spec.series == []
    assert spec.metadata["implemented"] is False
