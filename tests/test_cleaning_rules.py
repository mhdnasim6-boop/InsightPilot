"""Tests for the five built-in CleaningRule implementations, plus the shared rollback default."""

import pandas as pd

from backend.cleaning.rules.column_name_normalization_rule import (
    ColumnNameNormalizationRule,
)
from backend.cleaning.rules.data_type_normalization_rule import (
    DataTypeNormalizationRule,
)
from backend.cleaning.rules.duplicate_row_rule import DuplicateRowRule
from backend.cleaning.rules.missing_value_rule import MissingValueRule
from backend.cleaning.rules.whitespace_cleanup_rule import WhitespaceCleanupRule


def test_missing_value_rule_validate_false_when_no_missing() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})
    assert MissingValueRule().validate(df) is False


def test_missing_value_rule_apply_drops_rows_by_default() -> None:
    df = pd.DataFrame({"a": [1, None, 3]})
    rule = MissingValueRule()

    result, step = rule.apply(df)

    assert result.shape[0] == 2
    assert step.rule_name == "missing_value_rule"
    assert step.rows_before == 3
    assert step.rows_after == 2
    assert isinstance(step.description, str) and step.description


def test_missing_value_rule_rollback_returns_original() -> None:
    original = pd.DataFrame({"a": [1, None, 3]})
    rule = MissingValueRule()
    updated, _ = rule.apply(original)

    rolled_back = rule.rollback(updated, original)

    assert rolled_back.equals(original)


def test_duplicate_row_rule_validate_and_apply() -> None:
    df = pd.DataFrame({"a": [1, 1, 2]})
    rule = DuplicateRowRule()

    assert rule.validate(df) is True

    result, step = rule.apply(df)

    assert result.shape[0] == 2
    assert step.details["duplicates_removed"] == 1


def test_duplicate_row_rule_validate_false_without_duplicates() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})
    assert DuplicateRowRule().validate(df) is False


def test_column_name_normalization_rule() -> None:
    df = pd.DataFrame({" Region ": [1], "Amount$": [2]})
    rule = ColumnNameNormalizationRule()

    assert rule.validate(df) is True

    result, step = rule.apply(df)

    assert list(result.columns) == ["region", "amount"]
    assert set(step.columns_affected) == {" Region ", "Amount$"}


def test_column_name_normalization_rule_validate_false_when_already_clean() -> None:
    df = pd.DataFrame({"region": [1]})
    assert ColumnNameNormalizationRule().validate(df) is False


def test_whitespace_cleanup_rule() -> None:
    df = pd.DataFrame({"name": [" a ", "b"], "amount": [1, 2]})
    rule = WhitespaceCleanupRule()

    assert rule.validate(df) is True

    result, step = rule.apply(df)

    assert result["name"].tolist() == ["a", "b"]
    assert step.columns_affected == ["name"]


def test_data_type_normalization_rule_with_explicit_map() -> None:
    df = pd.DataFrame({"a": ["1", "2"]})
    rule = DataTypeNormalizationRule(dtype_map={"a": "int64"})

    assert rule.validate(df) is True

    result, step = rule.apply(df)

    assert str(result["a"].dtype) == "int64"
    assert step.columns_affected == ["a"]


def test_data_type_normalization_rule_validate_false_when_disabled_and_no_map() -> None:
    df = pd.DataFrame({"a": ["x", "y"]})
    rule = DataTypeNormalizationRule(coerce_numeric_strings=False)
    assert rule.validate(df) is False


def test_rule_description_is_non_empty_for_every_built_in_rule() -> None:
    rules = [
        MissingValueRule(),
        DuplicateRowRule(),
        ColumnNameNormalizationRule(),
        DataTypeNormalizationRule(),
        WhitespaceCleanupRule(),
    ]
    for rule in rules:
        assert isinstance(rule.description(), str)
        assert rule.description()
