"""Normalizes column names to lowercase snake_case."""

import pandas as pd

from backend.cleaning.models.result import CleaningStepRecord
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.transformations.column_names import normalize_column_names


class ColumnNameNormalizationRule(CleaningRule):
    """Renames columns to a consistent lowercase snake_case form."""

    name = "column_name_normalization_rule"

    def validate(self, dataframe: pd.DataFrame) -> bool:
        _, stats = normalize_column_names(dataframe)
        return bool(stats["rename_map"])

    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        rows_before = dataframe.shape[0]
        result, stats = normalize_column_names(dataframe)
        step = CleaningStepRecord(
            rule_name=self.name,
            description=self.description(),
            rows_before=rows_before,
            rows_after=result.shape[0],
            columns_affected=list(stats["rename_map"].keys()),
            details=stats,
        )
        return result, step

    def description(self) -> str:
        return "Normalizes column names to lowercase snake_case, deduplicating collisions."
