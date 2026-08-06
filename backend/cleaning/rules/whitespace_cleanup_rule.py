"""Strips leading/trailing whitespace from text column values."""

import pandas as pd

from backend.cleaning.models.result import CleaningStepRecord
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.transformations.whitespace import cleanup_whitespace


class WhitespaceCleanupRule(CleaningRule):
    """Strips leading/trailing whitespace from string-valued columns."""

    name = "whitespace_cleanup_rule"

    def __init__(self, columns: list[str] | None = None) -> None:
        self._columns = columns

    def validate(self, dataframe: pd.DataFrame) -> bool:
        target = self._columns or [
            column for column in dataframe.columns if not pd.api.types.is_numeric_dtype(dataframe[column])
        ]
        return len(target) > 0

    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        rows_before = dataframe.shape[0]
        result, stats = cleanup_whitespace(dataframe, self._columns)
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
        return "Strips leading/trailing whitespace from text column values."
