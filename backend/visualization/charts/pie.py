"""Pie chart generator: needs the raw DataFrame, reuses the analysis layer's AggregationEngine."""

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.models.aggregation import AggregationFunction
from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext

_OTHER_LABEL = "Other"


class PieChartGenerator(ChartGenerator):
    """Builds a pie chart of one numeric column summed by one categorical column.

    Categories beyond ``max_slices`` are combined into an "Other" slice —
    a pie with dozens of slivers is unreadable, so this keeps it usable.
    """

    chart_type = ChartType.PIE

    def __init__(self, aggregation_engine: AggregationEngine, max_slices: int = 8) -> None:
        self._aggregation_engine = aggregation_engine
        self._max_slices = max_slices

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if context.dataframe is None:
            return False, "No dataset provided; pie chart requires the raw DataFrame."
        categorical, numeric = self._usable_columns(context)
        if not categorical or not numeric:
            return False, "No categorical + numeric column pair available."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        dataframe = context.dataframe
        assert dataframe is not None  # applicable() already confirmed this
        categorical, numeric = self._usable_columns(context)

        category_column = min(categorical, key=lambda column: dataframe[column].nunique())
        value_column = numeric[0]

        result = self._aggregation_engine.group_by(dataframe, category_column, value_column, AggregationFunction.SUM)
        ranked = sorted(
            ((key, value) for key, value in result.results.items() if value is not None),
            key=lambda pair: -pair[1],
        )

        top = ranked[: self._max_slices]
        rest_total = sum(value for _, value in ranked[self._max_slices :])
        labels = [key for key, _ in top]
        values = [value for _, value in top]
        if rest_total > 0:
            labels.append(_OTHER_LABEL)
            values.append(rest_total)

        series = ChartSeries(name=value_column, x=labels, y=values)
        return ChartSpecification(
            chart_id=f"pie_{generate_id()}",
            title=f"{value_column} share by {category_column}",
            chart_type=ChartType.PIE,
            series=[series],
            description=f"Share of total {value_column} by {category_column}.",
            priority=6,
        )

    def _usable_columns(self, context: ChartContext) -> tuple[list[str], list[str]]:
        dataframe = context.dataframe
        if dataframe is None:
            return [], []
        summary = context.analysis_result.dataset_summary
        categorical = [column for column in summary.categorical_columns if column in dataframe.columns]
        numeric = [column for column in summary.numeric_columns if column in dataframe.columns]
        return categorical, numeric
