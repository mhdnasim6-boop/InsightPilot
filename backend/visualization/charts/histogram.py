"""Histogram generator: needs the raw DataFrame."""

import numpy as np

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


class HistogramGenerator(ChartGenerator):
    """Builds a binned frequency histogram for the first available numeric column."""

    chart_type = ChartType.HISTOGRAM

    def __init__(self, bins: int = 10) -> None:
        self._bins = bins

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if context.dataframe is None:
            return False, "No dataset provided; histogram requires the raw DataFrame."
        if not self._usable_numeric_columns(context):
            return False, "No numeric columns available."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        dataframe = context.dataframe
        assert dataframe is not None  # applicable() already confirmed this
        column = self._usable_numeric_columns(context)[0]

        values = dataframe[column].dropna()
        counts, edges = np.histogram(values, bins=self._bins)
        labels = [f"{edges[index]:.2f}-{edges[index + 1]:.2f}" for index in range(len(edges) - 1)]

        series = ChartSeries(name=column, x=labels, y=to_jsonable(counts.tolist()))
        return ChartSpecification(
            chart_id=f"histogram_{generate_id()}",
            title=f"Distribution of {column}",
            chart_type=ChartType.HISTOGRAM,
            x_axis=AxisSpec(label=column, column=column, data_type="numeric"),
            y_axis=AxisSpec(label="Frequency"),
            series=[series],
            description=f"Frequency distribution of {column} across {self._bins} bins.",
            priority=4,
        )

    def _usable_numeric_columns(self, context: ChartContext) -> list[str]:
        dataframe = context.dataframe
        if dataframe is None:
            return []
        return [column for column in context.analysis_result.dataset_summary.numeric_columns if column in dataframe.columns]
