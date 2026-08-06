"""Organizes a list of ChartSpecifications into one of four layout templates."""

from collections.abc import Callable

from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.layout import Layout, LayoutSection, LayoutType

_CATEGORY_TITLES: dict[str, str] = {
    "kpi": "Key Metrics",
    "trend": "Trends",
    "relationship": "Relationships",
    "distribution": "Distributions",
    "category": "Categories",
}

_CATEGORY_CHART_TYPES: dict[str, set[ChartType]] = {
    "kpi": {ChartType.KPI_CARD},
    "trend": {ChartType.LINE},
    "relationship": {ChartType.SCATTER, ChartType.HEATMAP, ChartType.CORRELATION_MATRIX},
    "distribution": {ChartType.HISTOGRAM, ChartType.BOX, ChartType.DISTRIBUTION},
    "category": {ChartType.BAR, ChartType.PIE, ChartType.TREEMAP},
}


class LayoutEngine:
    """Builds a ``Layout`` (named, ordered chart-ID sections) for a chosen ``LayoutType``."""

    def __init__(self, highlight_count: int = 3) -> None:
        self._highlight_count = highlight_count
        self._builders: dict[LayoutType, Callable[[list[ChartSpecification]], Layout]] = {
            LayoutType.EXECUTIVE_SUMMARY: self._build_executive_summary,
            LayoutType.DETAILED_ANALYSIS: self._build_detailed_analysis,
            LayoutType.KPI_DASHBOARD: self._build_kpi_dashboard,
            LayoutType.COMPARISON_DASHBOARD: self._build_comparison_dashboard,
        }

    def build(self, layout_type: LayoutType, charts: list[ChartSpecification]) -> Layout:
        """Organize ``charts`` into the named layout ``layout_type`` describes."""
        return self._builders[layout_type](charts)

    def _grouped(self, charts: list[ChartSpecification]) -> dict[str, list[ChartSpecification]]:
        groups: dict[str, list[ChartSpecification]] = {key: [] for key in _CATEGORY_CHART_TYPES}
        for chart in charts:
            for key, types in _CATEGORY_CHART_TYPES.items():
                if chart.chart_type in types:
                    groups[key].append(chart)
                    break
        return groups

    def _section(self, title: str, charts: list[ChartSpecification], columns: int = 2) -> LayoutSection:
        return LayoutSection(title=title, chart_ids=[chart.chart_id for chart in charts], columns=columns)

    def _build_executive_summary(self, charts: list[ChartSpecification]) -> Layout:
        groups = self._grouped(charts)
        non_kpi = sorted(
            (chart for chart in charts if chart.chart_type != ChartType.KPI_CARD), key=lambda chart: -chart.priority
        )
        sections = []
        if groups["kpi"]:
            sections.append(self._section("Key Metrics", groups["kpi"], columns=4))
        if non_kpi:
            sections.append(self._section("Highlights", non_kpi[: self._highlight_count], columns=1))
        return Layout(layout_type=LayoutType.EXECUTIVE_SUMMARY, sections=sections)

    def _build_detailed_analysis(self, charts: list[ChartSpecification]) -> Layout:
        groups = self._grouped(charts)
        sections = [
            self._section(_CATEGORY_TITLES[key], groups[key], columns=4 if key == "kpi" else 2)
            for key in ("kpi", "trend", "relationship", "distribution", "category")
            if groups[key]
        ]
        return Layout(layout_type=LayoutType.DETAILED_ANALYSIS, sections=sections)

    def _build_kpi_dashboard(self, charts: list[ChartSpecification]) -> Layout:
        groups = self._grouped(charts)
        rest = [chart for chart in charts if chart.chart_type != ChartType.KPI_CARD]
        sections = []
        if groups["kpi"]:
            sections.append(self._section("Key Metrics", groups["kpi"], columns=4))
        if rest:
            sections.append(self._section("Supporting Charts", rest, columns=2))
        return Layout(layout_type=LayoutType.KPI_DASHBOARD, sections=sections)

    def _build_comparison_dashboard(self, charts: list[ChartSpecification]) -> Layout:
        comparison_types = _CATEGORY_CHART_TYPES["category"]
        comparisons = [chart for chart in charts if chart.chart_type in comparison_types]
        rest = [chart for chart in charts if chart.chart_type not in comparison_types]
        sections = []
        if comparisons:
            sections.append(self._section("Comparisons", comparisons, columns=2))
        if rest:
            sections.append(self._section("Additional Detail", rest, columns=2))
        return Layout(layout_type=LayoutType.COMPARISON_DASHBOARD, sections=sections)
