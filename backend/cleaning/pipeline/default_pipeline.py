"""Assembles the default cleaning pipeline: a sensible, documented rule order."""

from backend.cleaning.pipeline.pipeline import CleaningPipeline
from backend.cleaning.rules.column_name_normalization_rule import (
    ColumnNameNormalizationRule,
)
from backend.cleaning.rules.data_type_normalization_rule import (
    DataTypeNormalizationRule,
)
from backend.cleaning.rules.duplicate_row_rule import DuplicateRowRule
from backend.cleaning.rules.missing_value_rule import MissingValueRule
from backend.cleaning.rules.whitespace_cleanup_rule import WhitespaceCleanupRule


def build_default_pipeline() -> CleaningPipeline:
    """Build the default rule pipeline.

    Order: normalize names and whitespace first (so later rules and any
    caller-supplied column lists see clean labels/values), then handle
    missing values, then duplicates, then dtype normalization last (dtype
    coercion benefits from already-trimmed strings).
    """
    return CleaningPipeline(
        [
            ColumnNameNormalizationRule(),
            WhitespaceCleanupRule(),
            MissingValueRule(),
            DuplicateRowRule(),
            DataTypeNormalizationRule(),
        ]
    )
