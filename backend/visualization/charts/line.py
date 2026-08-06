"""Line chart generator: built entirely from AnalysisResult.trends — no DataFrame needed."""

from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext


class LineChartGenerator(ChartGenerator):
    """Builds a rolling-average line chart for every trending numeric column."""

    chart_type = ChartType.LINE

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        trends = context.analysis_result.trends
        if not trends.applicable or not trends.series:
            return False, trends.reason or "No trend series available."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        trends = context.analysis_result.trends
        series = [
            ChartSeries(
                name=trend.column,
                y=trend.rolling_average,
                metadata={"growth_rate": trend.growth_rate},
            )
            for trend in trends.series
        ]
        return ChartSpecification(
            chart_id=f"line_{generate_id()}",
            title=f"Trend over {trends.time_column}",
            chart_type=ChartType.LINE,
            x_axis=AxisSpec(label=trends.time_column or "Time", column=trends.time_column, data_type="datetime"),
            y_axis=AxisSpec(label="Rolling Average", data_type="numeric"),
            series=series,
            description=(
                f"Rolling average (window={trends.window}) for {len(series)} numeric column(s) "
                f"over {trends.time_column}."
            ),
            priority=8,
        )
