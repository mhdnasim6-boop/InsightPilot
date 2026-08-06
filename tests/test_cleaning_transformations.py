"""Tests for the pure pandas transformation functions."""

import pandas as pd

from backend.cleaning.transformations.column_names import (
    normalize_column_name,
    normalize_column_names,
)
from backend.cleaning.transformations.data_types import normalize_data_types
from backend.cleaning.transformations.duplicates import remove_duplicate_rows
from backend.cleaning.transformations.missing_values import handle_missing_values
from backend.cleaning.transformations.whitespace import cleanup_whitespace


def test_normalize_column_name_lowercases_and_replaces_unsafe_chars() -> None:
    assert normalize_column_name(" Region Name! ") == "region_name"
    assert normalize_column_name("Amount$") == "amount"
    assert normalize_column_name("   ") == "unnamed_column"


def test_normalize_column_names_dedupes_collisions() -> None:
    df = pd.DataFrame([[1, 2, 3]], columns=["Region", "region", "REGION!"])

    result, stats = normalize_column_names(df)

    assert list(result.columns) == ["region", "region_2", "region_3"]
    assert stats["rename_map"] == {"Region": "region", "region": "region_2", "REGION!": "region_3"}


def test_normalize_column_names_no_op_when_already_normalized() -> None:
    df = pd.DataFrame({"region": [1], "amount": [2]})
    result, stats = normalize_column_names(df)
    assert stats["rename_map"] == {}
    assert list(result.columns) == ["region", "amount"]


def test_remove_duplicate_rows_default_keeps_first() -> None:
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})

    result, stats = remove_duplicate_rows(df)

    assert result.shape[0] == 2
    assert stats["duplicates_removed"] == 1


def test_remove_duplicate_rows_respects_subset() -> None:
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "y", "y"]})

    result, stats = remove_duplicate_rows(df, subset=["a"])

    assert result.shape[0] == 2
    assert stats["duplicates_removed"] == 1


def test_handle_missing_values_drop_rows() -> None:
    df = pd.DataFrame({"a": [1, None, 3]})

    result, stats = handle_missing_values(df, strategy="drop_rows")

    assert result.shape[0] == 2
    assert stats["rows_dropped"] == 1


def test_handle_missing_values_fill_constant() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0]})

    result, stats = handle_missing_values(df, strategy="fill_constant", fill_value=0.0)

    assert result["a"].tolist() == [1.0, 0.0, 3.0]
    assert stats["cells_filled"] == 1
    assert stats["columns_affected"] == ["a"]


def test_handle_missing_values_fill_mean_skips_non_numeric_columns() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0], "name": ["x", None, "z"]})

    result, stats = handle_missing_values(df, strategy="fill_mean")

    assert result["a"].tolist() == [1.0, 2.0, 3.0]
    assert result["name"].isna().sum() == 1  # non-numeric column untouched
    assert stats["columns_affected"] == ["a"]


def test_handle_missing_values_fill_mode() -> None:
    df = pd.DataFrame({"a": ["x", "x", None, "y"]})

    result, _ = handle_missing_values(df, strategy="fill_mode")

    assert result["a"].tolist() == ["x", "x", "x", "y"]


def test_cleanup_whitespace_strips_string_values_only() -> None:
    df = pd.DataFrame({"name": [" a ", "b", " c"], "amount": [1, 2, 3]})

    result, stats = cleanup_whitespace(df)

    assert result["name"].tolist() == ["a", "b", "c"]
    assert result["amount"].tolist() == [1, 2, 3]
    assert stats["columns_affected"] == ["name"]


def test_cleanup_whitespace_no_op_when_already_clean() -> None:
    df = pd.DataFrame({"name": ["a", "b"]})
    _, stats = cleanup_whitespace(df)
    assert stats["columns_affected"] == []


def test_normalize_data_types_explicit_map() -> None:
    df = pd.DataFrame({"a": ["1", "2", "3"]})

    result, stats = normalize_data_types(df, dtype_map={"a": "int64"})

    assert str(result["a"].dtype) == "int64"
    assert stats["columns_affected"] == ["a"]


def test_normalize_data_types_coerces_fully_numeric_string_column() -> None:
    df = pd.DataFrame({"a": ["1", "2", "3"], "b": ["x", "y", "z"]})

    result, stats = normalize_data_types(df)

    assert pd.api.types.is_numeric_dtype(result["a"])
    assert not pd.api.types.is_numeric_dtype(result["b"])
    assert stats["columns_affected"] == ["a"]


def test_normalize_data_types_does_not_coerce_partially_numeric_column() -> None:
    df = pd.DataFrame({"a": ["1", "two", "3"]})

    result, stats = normalize_data_types(df)

    assert not pd.api.types.is_numeric_dtype(result["a"])
    assert stats["columns_affected"] == []
