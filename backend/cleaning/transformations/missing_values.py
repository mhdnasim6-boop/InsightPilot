"""Deterministic missing-value handling: drop or fill, no inference of intent."""

from typing import Any, Literal

import pandas as pd

MissingValueStrategy = Literal["drop_rows", "fill_constant", "fill_mean", "fill_median", "fill_mode"]


def handle_missing_values(
    dataframe: pd.DataFrame,
    strategy: MissingValueStrategy = "drop_rows",
    fill_value: Any = None,
    columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply one missing-value strategy to ``dataframe`` (or a column subset).

    ``fill_mean``/``fill_median`` silently skip non-numeric columns rather
    than raising — a caller passing "all columns" (the default) shouldn't
    have to know which ones are numeric in advance.
    """
    subset = [column for column in (columns or list(dataframe.columns)) if column in dataframe.columns]

    if strategy == "drop_rows":
        rows_before = dataframe.shape[0]
        result = dataframe.dropna(subset=subset) if subset else dataframe.copy()
        return result, {"rows_dropped": rows_before - result.shape[0], "columns_affected": []}

    result = dataframe.copy()
    cells_filled = 0
    columns_affected: list[str] = []
    for column in subset:
        missing_before = int(result[column].isna().sum())
        if missing_before == 0:
            continue

        if strategy == "fill_constant":
            result[column] = result[column].fillna(fill_value)
        elif strategy in ("fill_mean", "fill_median"):
            if not pd.api.types.is_numeric_dtype(result[column]):
                continue
            statistic = result[column].mean() if strategy == "fill_mean" else result[column].median()
            result[column] = result[column].fillna(statistic)
        elif strategy == "fill_mode":
            mode = result[column].mode(dropna=True)
            if mode.empty:
                continue
            result[column] = result[column].fillna(mode.iloc[0])

        cells_filled += missing_before
        columns_affected.append(column)

    return result, {"cells_filled": cells_filled, "columns_affected": columns_affected}
