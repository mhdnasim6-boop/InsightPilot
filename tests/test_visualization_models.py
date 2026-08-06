"""Tests for visualization models: shapes, defaults, and VisualizationResult."""

from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.layout import Layout, LayoutSection, LayoutType
from backend.visualization.models.placeholder import ExportPlaceholder
from backend.visualization.models.recommendation import (
    RecommendationResult,
    SkippedChart,
)
from backend.visualization.models.result import VisualizationResult
from backend.visualization.models.theme import Theme


def test_chart_series_defaults() -> None:
    series = ChartSeries(name="s1")
    assert series.x == []
    assert series.y == []
    assert series.z is None
    assert series.metadata == {}


def test_chart_specification_defaults() -> None:
    spec = ChartSpecification(chart_id="c1", title="Chart", chart_type=ChartType.BAR)
    assert spec.x_axis is None
    assert spec.series == []
    assert spec.filters == []
    assert spec.priority == 0
    assert spec.interactive is True
    assert spec.metadata == {}


def test_chart_specification_carries_axes_and_series() -> None:
    spec = ChartSpecification(
        chart_id="c1",
        title="Revenue by Region",
        chart_type=ChartType.BAR,
        x_axis=AxisSpec(label="Region", column="region", data_type="categorical"),
        y_axis=AxisSpec(label="Revenue", column="revenue", data_type="numeric"),
        series=[ChartSeries(name="revenue", x=["East", "West"], y=[100, 50])],
        priority=6,
    )
    assert spec.x_axis is not None
    assert spec.x_axis.column == "region"
    assert spec.series[0].y == [100, 50]


def test_chart_type_covers_all_eleven_supported_types() -> None:
    assert {member.value for member in ChartType} == {
        "bar",
        "line",
        "scatter",
        "histogram",
        "box",
        "pie",
        "heatmap",
        "correlation_matrix",
        "distribution",
        "kpi_card",
        "treemap",
    }


def test_skipped_chart_and_recommendation_result() -> None:
    skipped = SkippedChart(chart_type=ChartType.SCATTER, reason="Fewer than two numeric columns available.")
    result = RecommendationResult(charts=[], skipped=[skipped])
    assert result.charts == []
    assert result.skipped[0].reason == "Fewer than two numeric columns available."


def test_layout_section_and_layout_defaults() -> None:
    section = LayoutSection(title="Key Metrics", chart_ids=["kpi_1"])
    assert section.columns == 2
    layout = Layout(layout_type=LayoutType.EXECUTIVE_SUMMARY, sections=[section])
    assert layout.sections[0].title == "Key Metrics"


def test_theme_shape() -> None:
    theme = Theme(name="light", background_color="#fff", font_color="#000", grid_color="#eee")
    assert theme.color_palette == []


def test_export_placeholder_defaults_to_not_implemented() -> None:
    placeholder = ExportPlaceholder(format="png", note="not implemented")
    assert placeholder.implemented is False


def test_visualization_result_bundles_everything() -> None:
    layout = Layout(layout_type=LayoutType.DETAILED_ANALYSIS, sections=[])
    result = VisualizationResult(
        visualization_id="v1",
        analysis_id="a1",
        layout=layout,
        execution_time=0.01,
    )
    assert result.charts == []
    assert result.recommendations == []
    assert result.warnings == []
    assert result.metadata == {}
