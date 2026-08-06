"""Distribution plot generator: needs the raw DataFrame, enriched with descriptive statistics."""

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


class DistributionPlotGenerator(ChartGenerator):
    """Builds a per-column value distribution, annotated with skewness/kurtosis."""

    chart_type = ChartType.DISTRIBUTION

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if context.dataframe is None:
            return False, "No dataset provided; distribution plot requires the raw DataFrame."
        if not self._usable_numeric_columns(context):
            return False, "No numeric columns available."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        dataframe = context.dataframe
        assert dataframe is not None  # applicable() already confirmed this
        stats_by_column = context.analysis_result.descriptive_statistics.columns
        numeric = self._usable_numeric_columns(context)

        series = []
        for column in numeric:
            column_stats = stats_by_column.get(column)
            metadata = (
                {
                    "skewness": column_stats.distribution_summary.get("skewness"),
                    "kurtosis": column_stats.distribution_summary.get("kurtosis"),
                }
                if column_stats
                else {}
            )
            series.append(
                ChartSeries(name=column, x=to_jsonable(dataframe[column].dropna().tolist()), metadata=metadata)
            )

        return ChartSpecification(
            chart_id=f"distribution_{generate_id()}",
            title="Value Distributions",
            chart_type=ChartType.DISTRIBUTION,
            x_axis=AxisSpec(label="Value", data_type="numeric"),
            series=series,
            description=f"Value distribution (with skewness/kurtosis) for {len(series)} numeric column(s).",
            priority=4,
        )

    def _usable_numeric_columns(self, context: ChartContext) -> list[str]:
        dataframe = context.dataframe
        if dataframe is None:
            return []
        return [column for column in context.analysis_result.dataset_summary.numeric_columns if column in dataframe.columns]
