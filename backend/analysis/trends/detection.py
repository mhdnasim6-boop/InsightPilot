"""Deterministic time-column detection.

Mechanical, not AI: prefers an actual datetime-dtype column, then falls
back to a column name that looks like a time/date field — the same
keyword-matching style already used for planner prompt-category selection.
"""

import pandas as pd

_TIME_KEYWORDS = ("date", "time", "timestamp", "period", "year", "month")


def detect_time_column(dataframe: pd.DataFrame) -> str | None:
    """Return the best candidate time column in ``dataframe``, or None if none is found."""
    for column in dataframe.columns:
        if pd.api.types.is_datetime64_any_dtype(dataframe[column]):
            return str(column)

    for column in dataframe.columns:
        lowered = str(column).lower()
        if any(keyword in lowered for keyword in _TIME_KEYWORDS):
            return str(column)

    return None
