"""Tests for ingestion validation: shared checks and the composite DatasetValidator."""

from pathlib import Path

import pandas as pd

from backend.ingestion.validators.checks import (
    check_dataframe,
    check_extension,
    check_source_file,
)
from backend.ingestion.validators.validator import DatasetValidator


def test_check_extension_flags_unknown_extension() -> None:
    issues = check_extension("/data/report.pdf", known_extensions={".csv", ".xlsx"})
    assert len(issues) == 1
    assert issues[0].code == "unsupported_extension"


def test_check_extension_passes_known_extension() -> None:
    assert check_extension("/data/report.csv", known_extensions={".csv", ".xlsx"}) == []


def test_check_source_file_flags_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.csv"
    issues = check_source_file(str(missing))
    assert len(issues) == 1
    assert issues[0].code == "source_not_found"


def test_check_source_file_flags_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")

    issues = check_source_file(str(empty_file))

    assert len(issues) == 1
    assert issues[0].code == "empty_file"


def test_check_source_file_passes_a_real_non_empty_file(tmp_path: Path) -> None:
    real_file = tmp_path / "data.csv"
    real_file.write_text("a,b\n1,2\n")

    assert check_source_file(str(real_file)) == []


def test_check_dataframe_flags_no_columns() -> None:
    issues = check_dataframe(pd.DataFrame())
    assert any(issue.code == "invalid_schema" for issue in issues)


def test_check_dataframe_flags_empty_dataset_as_warning_only() -> None:
    issues = check_dataframe(pd.DataFrame({"a": pd.Series([], dtype="int64")}))
    assert len(issues) == 1
    assert issues[0].code == "empty_dataset"
    assert issues[0].severity.value == "warning"


def test_check_dataframe_flags_duplicate_columns() -> None:
    df = pd.DataFrame([[1, 2]])
    df.columns = ["a", "a"]

    issues = check_dataframe(df)

    assert any(issue.code == "duplicate_columns" for issue in issues)


def test_check_dataframe_passes_a_well_formed_dataframe() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    assert check_dataframe(df) == []


def test_dataset_validator_composite_valid_case(tmp_path: Path) -> None:
    real_file = tmp_path / "data.csv"
    real_file.write_text("a,b\n1,2\n")
    df = pd.DataFrame({"a": [1], "b": [2]})

    result = DatasetValidator().validate(str(real_file), known_extensions={".csv"}, dataframe=df)

    assert result.is_valid is True
    assert result.errors == []


def test_dataset_validator_composite_reports_multiple_issues(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"

    result = DatasetValidator().validate(str(missing), known_extensions={".csv"})

    assert result.is_valid is False
    codes = {issue.code for issue in result.errors}
    assert "unsupported_extension" in codes
    assert "source_not_found" in codes


def test_validate_dataframe_passes_a_well_formed_dataframe() -> None:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

    result = DatasetValidator().validate_dataframe(df)

    assert result.is_valid is True
    assert result.errors == []


def test_validate_dataframe_flags_no_columns_with_no_file_involved() -> None:
    """The non-file counterpart to validate(): no source_location/extension to check, only shape."""
    result = DatasetValidator().validate_dataframe(pd.DataFrame())

    assert result.is_valid is False
    assert any(issue.code == "invalid_schema" for issue in result.errors)
