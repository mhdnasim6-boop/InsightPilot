"""Handles missing values via a configurable, deterministic strategy."""

from typing import Any

import pandas as pd

from backend.cleaning.models.result import CleaningStepRecord
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.transformations.missing_values import (
    MissingValueStrategy,
    handle_missing_values,
)


class MissingValueRule(CleaningRule):
    """Drops rows with missing values, or fills them, per the configured strategy."""

    name = "missing_value_rule"

    def __init__(
        self,
        strategy: MissingValueStrategy = "drop_rows",
        fill_value: Any = None,
        columns: list[str] | None = None,
    ) -> None:
        self._strategy = strategy
        self._fill_value = fill_value
        self._columns = columns

    def validate(self, dataframe: pd.DataFrame) -> bool:
        subset = [column for column in (self._columns or list(dataframe.columns)) if column in dataframe.columns]
        if not subset:
            return False
        return bool(dataframe[subset].isna().to_numpy().any())

    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        rows_before = dataframe.shape[0]
        result, stats = handle_missing_values(dataframe, self._strategy, self._fill_value, self._columns)
        step = CleaningStepRecord(
            rule_name=self.name,
            description=self.description(),
            rows_before=rows_before,
            rows_after=result.shape[0],
            columns_affected=stats.get("columns_affected", []),
            details=stats,
        )
        return result, step

    def description(self) -> str:
        return f"Handles missing values using strategy '{self._strategy}'."
