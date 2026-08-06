"""Removes duplicate rows."""

from typing import Any, Literal

import pandas as pd


def remove_duplicate_rows(
    dataframe: pd.DataFrame,
    subset: list[str] | None = None,
    keep: Literal["first", "last"] = "first",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Drop duplicate rows (optionally scoped to ``subset`` columns)."""
    rows_before = dataframe.shape[0]
    result = dataframe.drop_duplicates(subset=subset, keep=keep)
    return result, {"duplicates_removed": rows_before - result.shape[0], "columns_affected": []}
