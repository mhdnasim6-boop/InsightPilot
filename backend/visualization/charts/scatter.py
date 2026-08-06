"""Scatter plot generator: needs the raw DataFrame; prefers the strongest correlated pair."""

from backend.analysis.models.correlation import (
    CorrelationAnalysisResult,
    CorrelationPair,
)
from backend.ingestion.metadata.json_safe import to_jsonable
from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext


class ScatterPlotGenerator(ChartGenerator):
    """Builds a scatter plot for two numeric columns, preferring the strongest correlated pair."""

    chart_type = ChartType.SCATTER

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if context.dataframe is None:
            return False, "No dataset provided; scatter plot requires the raw DataFrame."
        if len(self._usable_numeric_columns(context)) < 2:
            return False, "Fewer than two numeric columns available."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        dataframe = context.dataframe
        assert dataframe is not None  # applicable() already confirmed this
        numeric = self._usable_numeric_columns(context)
        x_column, y_column = self._pick_pair(context.analysis_result.correlations, numeric)

        subset = dataframe[[x_column, y_column]].dropna()
        series = ChartSeries(
            name=f"{x_column} vs {y_column}",
            x=to_jsonable(subset[x_column].tolist()),
            y=to_jsonable(subset[y_column].tolist()),
        )
        return ChartSpecification(
            chart_id=f"scatter_{generate_id()}",
            title=f"{y_column} vs {x_column}",
            chart_type=ChartType.SCATTER,
            x_axis=AxisSpec(label=x_column, column=x_column, data_type="numeric"),
            y_axis=AxisSpec(label=y_column, column=y_column, data_type="numeric"),
            series=[series],
            description=f"Relationship between {x_column} and {y_column}.",
            priority=5,
        )

    def _usable_numeric_columns(self, context: ChartContext) -> list[str]:
        dataframe = context.dataframe
        if dataframe is None:
            return []
        return [column for column in context.analysis_result.dataset_summary.numeric_columns if column in dataframe.columns]

    def _pick_pair(self, correlations: CorrelationAnalysisResult, numeric: list[str]) -> tuple[str, str]:
        if correlations.applicable:
            pairs: list[CorrelationPair] = [*correlations.strong_positive, *correlations.strong_negative]
            candidates = [pair for pair in pairs if pair.column_a in numeric and pair.column_b in numeric]
            if candidates:
                best = max(candidates, key=lambda pair: abs(pair.pearson or 0.0))
                return best.column_a, best.column_b
        return numeric[0], numeric[1]
