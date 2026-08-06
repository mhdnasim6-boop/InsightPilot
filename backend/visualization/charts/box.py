"""Box plot generator: built entirely from AnalysisResult.descriptive_statistics
(already-computed min/quartiles/max) — no DataFrame needed.
"""

from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext


class BoxPlotGenerator(ChartGenerator):
    """Builds a box plot (min/Q1/median/Q3/max per column) from descriptive statistics."""

    chart_type = ChartType.BOX

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if not context.analysis_result.descriptive_statistics.columns:
            return False, "No numeric columns available for a box plot."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        columns = context.analysis_result.descriptive_statistics.columns
        series = [
            ChartSeries(
                name=column,
                metadata={
                    "min": stats.minimum,
                    "q1": stats.quartiles.get("q1"),
                    "median": stats.quartiles.get("q2"),
                    "q3": stats.quartiles.get("q3"),
                    "max": stats.maximum,
                    "mean": stats.mean,
                    "std": stats.std,
                },
            )
            for column, stats in columns.items()
        ]
        return ChartSpecification(
            chart_id=f"box_{generate_id()}",
            title="Distribution Summary (Box Plot)",
            chart_type=ChartType.BOX,
            y_axis=AxisSpec(label="Value", data_type="numeric"),
            series=series,
            description=f"Min/Q1/Median/Q3/Max for {len(series)} numeric column(s).",
            priority=5,
        )
