"""Casts explicitly mapped columns and coerces cleanly-numeric string columns."""

import pandas as pd

from backend.cleaning.models.result import CleaningStepRecord
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.transformations.data_types import normalize_data_types


class DataTypeNormalizationRule(CleaningRule):
    """Casts columns per an explicit dtype map and/or coerces clean numeric-string columns."""

    name = "data_type_normalization_rule"

    def __init__(self, dtype_map: dict[str, str] | None = None, coerce_numeric_strings: bool = True) -> None:
        self._dtype_map = dtype_map
        self._coerce_numeric_strings = coerce_numeric_strings

    def validate(self, dataframe: pd.DataFrame) -> bool:
        if self._dtype_map:
            return True
        if not self._coerce_numeric_strings:
            return False
        return any(not pd.api.types.is_numeric_dtype(dataframe[column]) for column in dataframe.columns)

    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        rows_before = dataframe.shape[0]
        result, stats = normalize_data_types(dataframe, self._dtype_map, self._coerce_numeric_strings)
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
        return "Casts explicitly mapped columns and coerces cleanly-numeric string columns to numeric dtypes."
