"""Group-by and pivot-style aggregation, dict-dispatched (no if/else chains)."""

from typing import Any

import pandas as pd

from backend.analysis.models.aggregation import (
    AggregationFunction,
    AggregationResult,
    PivotResult,
)
from backend.ingestion.metadata.json_safe import to_jsonable

_AGG_METHOD: dict[AggregationFunction, str] = {
    AggregationFunction.COUNT: "count",
    AggregationFunction.SUM: "sum",
    AggregationFunction.AVERAGE: "mean",
    AggregationFunction.MEDIAN: "median",
    AggregationFunction.MINIMUM: "min",
    AggregationFunction.MAXIMUM: "max",
}


class AggregationEngine:
    """Group-by and pivot-style summaries, reusable by any future dashboard/report module."""

    def group_by(
        self,
        dataframe: pd.DataFrame,
        group_column: str,
        value_column: str | None,
        aggregation: AggregationFunction,
    ) -> AggregationResult:
        """Group ``dataframe`` by ``group_column`` and aggregate ``value_column``.

        ``value_column=None`` is only meaningful with ``COUNT`` — it counts
        rows per group regardless of any particular column.
        """
        grouped = dataframe.groupby(group_column)
        if value_column is None:
            series = grouped.size() if aggregation == AggregationFunction.COUNT else None
        else:
            method = _AGG_METHOD[aggregation]
            series = getattr(grouped[value_column], method)()

        results: dict[str, Any] = {str(key): to_jsonable(value) for key, value in series.to_dict().items()} if series is not None else {}

        return AggregationResult(
            group_column=group_column, value_column=value_column, aggregation=aggregation, results=results
        )

    def pivot(
        self,
        dataframe: pd.DataFrame,
        index: str,
        columns: str,
        values: str,
        aggregation: AggregationFunction,
    ) -> PivotResult:
        """Build a pivot-style table: ``index`` rows x ``columns`` columns, aggregating ``values``."""
        method = _AGG_METHOD[aggregation]
        # pandas-stubs' aggfunc overloads are keyed on Literal method-name
        # strings; a caller-supplied plain `str` (looked up from our own
        # dict, one of the exact literal values pandas accepts at runtime)
        # can't statically match one specific overload, even though the
        # call itself is correct (empirically verified).
        table = pd.pivot_table(dataframe, index=index, columns=columns, values=values, aggfunc=method)  # type: ignore[arg-type]

        nested: dict[str, dict[str, Any]] = {
            str(row_key): {str(col_key): to_jsonable(value) for col_key, value in row.items()}
            for row_key, row in table.to_dict(orient="index").items()
        }

        return PivotResult(index=index, columns=columns, values=values, aggregation=aggregation, table=nested)
