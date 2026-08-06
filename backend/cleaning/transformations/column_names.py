"""Normalizes column names to a consistent lowercase snake_case form."""

import re
from typing import Any

import pandas as pd

_UNSAFE_CHARS = re.compile(r"[^0-9a-z_]+")


def normalize_column_name(name: str) -> str:
    """Return a lowercase, snake_case version of a single column name."""
    normalized = _UNSAFE_CHARS.sub("_", name.strip().lower()).strip("_")
    return normalized or "unnamed_column"


def normalize_column_names(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Rename every column to its normalized form, deduplicating any resulting collisions."""
    seen: dict[str, int] = {}
    rename_map: dict[Any, str] = {}
    for column in dataframe.columns:
        base = normalize_column_name(str(column))
        count = seen.get(base, 0)
        final_name = base if count == 0 else f"{base}_{count + 1}"
        seen[base] = count + 1
        rename_map[column] = final_name

    changed = {str(old): new for old, new in rename_map.items() if old != new}
    renamed = dataframe.rename(columns=rename_map)
    return renamed, {"rename_map": changed}
