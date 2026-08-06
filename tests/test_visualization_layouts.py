"""Tests for LayoutEngine: purely organizational chart grouping."""

from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.layout import LayoutType


def _chart(chart_id: str, chart_type: ChartType, priority: int = 0) -> ChartSpecification:
    return ChartSpecification(chart_id=chart_id, title=chart_id, chart_type=chart_type, priority=priority)


def _sample_charts() -> list[ChartSpecification]:
    return [
        _chart("kpi_1", ChartType.KPI_CARD, priority=10),
        _chart("line_1", ChartType.LINE, priority=8),
        _chart("corr_1", ChartType.CORRELATION_MATRIX, priority=7),
        _chart("bar_1", ChartType.BAR, priority=6),
        _chart("box_1", ChartType.BOX, priority=5),
        _chart("scatter_1", ChartType.SCATTER, priority=5),
        _chart("pie_1", ChartType.PIE, priority=4),
    ]


def test_executive_summary_has_key_metrics_and_capped_highlights() -> None:
    layout = LayoutEngine(highlight_count=2).build(LayoutType.EXECUTIVE_SUMMARY, _sample_charts())

    titles = [section.title for section in layout.sections]
    assert "Key Metrics" in titles
    assert "Highlights" in titles

    highlights = next(section for section in layout.sections if section.title == "Highlights")
    assert len(highlights.chart_ids) == 2
    assert highlights.chart_ids == ["line_1", "corr_1"]  # highest priority non-KPI charts


def test_detailed_analysis_groups_every_chart_by_category() -> None:
    layout = LayoutEngine().build(LayoutType.DETAILED_ANALYSIS, _sample_charts())

    all_chart_ids = {chart_id for section in layout.sections for chart_id in section.chart_ids}
    assert all_chart_ids == {chart.chart_id for chart in _sample_charts()}

    titles = [section.title for section in layout.sections]
    assert titles == ["Key Metrics", "Trends", "Relationships", "Distributions", "Categories"]


def test_kpi_dashboard_puts_kpis_first() -> None:
    layout = LayoutEngine().build(LayoutType.KPI_DASHBOARD, _sample_charts())

    assert layout.sections[0].title == "Key Metrics"
    assert layout.sections[0].chart_ids == ["kpi_1"]
    assert layout.sections[1].title == "Supporting Charts"


def test_comparison_dashboard_puts_category_charts_first() -> None:
    layout = LayoutEngine().build(LayoutType.COMPARISON_DASHBOARD, _sample_charts())

    assert layout.sections[0].title == "Comparisons"
    assert set(layout.sections[0].chart_ids) == {"bar_1", "pie_1"}
    assert layout.sections[1].title == "Additional Detail"


def test_layout_with_no_charts_produces_no_sections() -> None:
    layout = LayoutEngine().build(LayoutType.DETAILED_ANALYSIS, [])
    assert layout.sections == []
