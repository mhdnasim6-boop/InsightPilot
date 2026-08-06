"""Strips leading/trailing whitespace from string-valued columns."""

from typing import Any

import pandas as pd


def cleanup_whitespace(
    dataframe: pd.DataFrame, columns: list[str] | None = None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Strip leading/trailing whitespace from every value in the targeted columns."""
    target_columns = columns if columns is not None else [
        column for column in dataframe.columns if not pd.api.types.is_numeric_dtype(dataframe[column])
    ]

    result = dataframe.copy()
    affected: list[str] = []
    for column in target_columns:
        if column not in result.columns:
            continue
        original = result[column]
        cleaned = original.apply(lambda value: value.strip() if isinstance(value, str) else value)
        if not cleaned.equals(original):
            affected.append(column)
        result[column] = cleaned

    return result, {"columns_affected": affected}
