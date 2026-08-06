"""Removes duplicate rows."""

from typing import Literal

import pandas as pd

from backend.cleaning.models.result import CleaningStepRecord
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.transformations.duplicates import remove_duplicate_rows


class DuplicateRowRule(CleaningRule):
    """Removes duplicate rows, optionally scoped to a subset of columns."""

    name = "duplicate_row_rule"

    def __init__(self, subset: list[str] | None = None, keep: Literal["first", "last"] = "first") -> None:
        self._subset = subset
        self._keep = keep

    def validate(self, dataframe: pd.DataFrame) -> bool:
        return bool(dataframe.duplicated(subset=self._subset).any())

    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        rows_before = dataframe.shape[0]
        result, stats = remove_duplicate_rows(dataframe, self._subset, self._keep)
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
        scope = f" (subset={self._subset})" if self._subset else ""
        return f"Removes duplicate rows{scope}, keeping the '{self._keep}' occurrence."
