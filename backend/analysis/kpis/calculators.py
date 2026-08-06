"""Built-in calculators for the nine generic KPI types.

Every calculator has the same shape — ``(dataframe, definition) -> value``
— so a future business KPI's calculator (reading multi-column context from
``definition.params``) fits the exact same registry without any change to
``KPIEngine``.
"""

from collections.abc import Callable

import pandas as pd

from backend.analysis.models.kpi import KPIDefinition, KPIType
from backend.ingestion.metadata.json_safe import to_jsonable

KPICalculator = Callable[[pd.DataFrame, KPIDefinition], float | int | None]


def _column_series(dataframe: pd.DataFrame, definition: KPIDefinition) -> pd.Series | None:
    if definition.column is None or definition.column not in dataframe.columns:
        return None
    return dataframe[definition.column]


def calculate_record_count(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Total row count — the one KPI that never needs a column."""
    return int(dataframe.shape[0])


def calculate_null_percentage(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Percentage of missing values in the given column."""
    series = _column_series(dataframe, definition)
    if series is None or series.shape[0] == 0:
        return None
    return to_jsonable(round(float(series.isna().mean()) * 100, 2))


def calculate_distinct_count(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Number of distinct non-null values in the given column."""
    series = _column_series(dataframe, definition)
    if series is None:
        return None
    return int(series.nunique())


def calculate_average(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Arithmetic mean of the given numeric column (used for both AVERAGE and MEAN)."""
    series = _column_series(dataframe, definition)
    if series is None:
        return None
    return to_jsonable(series.mean())


def calculate_sum(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Sum of the given numeric column."""
    series = _column_series(dataframe, definition)
    if series is None:
        return None
    return to_jsonable(series.sum())


def calculate_minimum(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Minimum value of the given column."""
    series = _column_series(dataframe, definition)
    if series is None or series.empty:
        return None
    return to_jsonable(series.min())


def calculate_maximum(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Maximum value of the given column."""
    series = _column_series(dataframe, definition)
    if series is None or series.empty:
        return None
    return to_jsonable(series.max())


def calculate_median(dataframe: pd.DataFrame, definition: KPIDefinition) -> float | int | None:
    """Median value of the given numeric column."""
    series = _column_series(dataframe, definition)
    if series is None:
        return None
    return to_jsonable(series.median())


DEFAULT_CALCULATORS: dict[KPIType, KPICalculator] = {
    KPIType.RECORD_COUNT: calculate_record_count,
    KPIType.NULL_PERCENTAGE: calculate_null_percentage,
    KPIType.DISTINCT_COUNT: calculate_distinct_count,
    KPIType.AVERAGE: calculate_average,
    KPIType.SUM: calculate_sum,
    KPIType.MINIMUM: calculate_minimum,
    KPIType.MAXIMUM: calculate_maximum,
    KPIType.MEAN: calculate_average,
    KPIType.MEDIAN: calculate_median,
}
