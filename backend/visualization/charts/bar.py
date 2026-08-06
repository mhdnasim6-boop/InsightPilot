"""Bar chart generator: needs the raw DataFrame, reuses the analysis layer's AggregationEngine."""


from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.models.aggregation import AggregationFunction
from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext


class BarChartGenerator(ChartGenerator):
    """Builds a bar chart of one numeric column summed by one categorical column."""

    chart_type = ChartType.BAR

    def __init__(self, aggregation_engine: AggregationEngine, max_categories: int = 15) -> None:
        self._aggregation_engine = aggregation_engine
        self._max_categories = max_categories

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if context.dataframe is None:
            return False, "No dataset provided; bar chart requires the raw DataFrame."
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
        )[: self._max_categories]

        series = ChartSeries(name=value_column, x=[key for key, _ in ranked], y=[value for _, value in ranked])
        return ChartSpecification(
            chart_id=f"bar_{generate_id()}",
            title=f"{value_column} by {category_column}",
            chart_type=ChartType.BAR,
            x_axis=AxisSpec(label=category_column, column=category_column, data_type="categorical"),
            y_axis=AxisSpec(label=value_column, column=value_column, data_type="numeric"),
            series=[series],
            description=f"Sum of {value_column} grouped by {category_column}.",
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
