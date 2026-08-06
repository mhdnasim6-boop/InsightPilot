"""Casts explicitly mapped columns and coerces cleanly-numeric string columns.

"Cleanly-numeric" means every non-null value in the column converts
successfully — a strict, mechanical check, not a fuzzy inference of
intent.
"""

from typing import Any

import pandas as pd


def normalize_data_types(
    dataframe: pd.DataFrame,
    dtype_map: dict[str, str] | None = None,
    coerce_numeric_strings: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Cast ``dtype_map`` columns explicitly, then optionally coerce fully-numeric string columns."""
    result = dataframe.copy()
    affected: list[str] = []

    for column, dtype in (dtype_map or {}).items():
        if column not in result.columns:
            continue
        # pandas-stubs' astype() overloads are keyed on Literal dtype-name
        # strings; a caller-supplied plain `str` (any valid numpy/pandas
        # dtype name at runtime) can't statically match one specific
        # overload, even though the call itself is correct.
        result[column] = result[column].astype(dtype)  # type: ignore[call-overload]
        affected.append(column)

    if coerce_numeric_strings:
        mapped_columns = set(dtype_map or {})
        for column in result.columns:
            if column in mapped_columns or pd.api.types.is_numeric_dtype(result[column]):
                continue
            converted = pd.to_numeric(result[column], errors="coerce")
            non_null = result[column].notna()
            if non_null.any() and converted[non_null].notna().all():
                result[column] = converted
                affected.append(column)

    return result, {"columns_affected": affected}
