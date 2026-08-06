"""KPI card generator: built entirely from AnalysisResult.kpis — no DataFrame needed."""

from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext


class KPICardGenerator(ChartGenerator):
    """Builds one KPI-card chart whose series each represent a single KPI."""

    chart_type = ChartType.KPI_CARD

    def __init__(self, max_cards: int = 8) -> None:
        self._max_cards = max_cards

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if not context.analysis_result.kpis:
            return False, "No KPIs available."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        kpis = context.analysis_result.kpis[: self._max_cards]
        series = [
            ChartSeries(
                name=kpi.name,
                x=[kpi.name],
                y=[kpi.value],
                metadata={"kpi_type": kpi.kpi_type.value, "column": kpi.column},
            )
            for kpi in kpis
        ]
        return ChartSpecification(
            chart_id=f"kpi_cards_{generate_id()}",
            title="Key Performance Indicators",
            chart_type=ChartType.KPI_CARD,
            series=series,
            description=f"{len(series)} key performance indicator(s).",
            priority=10,
            interactive=False,
        )
