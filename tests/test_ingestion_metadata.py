"""Tests for MetadataExtractor, the JSON-safety helper, and the quality summary builder."""

import pandas as pd

from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.metadata.json_safe import to_jsonable
from backend.ingestion.metadata.quality import build_quality_summary
from backend.ingestion.validators.result import (
    DatasetValidationResult,
    IssueSeverity,
    ValidationIssue,
)


def test_to_jsonable_converts_nan_to_none() -> None:
    assert to_jsonable(float("nan")) is None


def test_to_jsonable_recurses_into_nested_structures() -> None:
    assert to_jsonable({"a": [1, float("nan"), {"b": float("nan")}]}) == {"a": [1, None, {"b": None}]}


def test_to_jsonable_passes_through_plain_values() -> None:
    assert to_jsonable("hello") == "hello"
    assert to_jsonable(5) == 5


def test_extractor_computes_columns_and_shape() -> None:
    df = pd.DataFrame({"age": [25, 30, 35], "name": ["a", "b", "c"]})

    result = MetadataExtractor().extract(df)

    assert result.row_count == 3
    assert result.column_count == 2
    assert {column.name for column in result.columns} == {"age", "name"}
    assert result.column_types["age"] == str(df["age"].dtype)
    assert result.memory_usage_bytes > 0


def test_extractor_counts_missing_values_per_column() -> None:
    df = pd.DataFrame({"age": [25, None, 35]})

    result = MetadataExtractor().extract(df)

    age_column = next(column for column in result.columns if column.name == "age")
    assert age_column.null_count == 1
    assert age_column.non_null_count == 2


def test_extractor_sample_rows_and_statistics_are_json_safe() -> None:
    df = pd.DataFrame({"age": [25, None], "name": ["a", "b"]})

    result = MetadataExtractor().extract(df, sample_size=2)

    assert result.sample_rows[0] == {"age": 25.0, "name": "a"}
    assert result.sample_rows[1]["age"] is None  # NaN sanitized to None
    assert "age" in result.statistics


def test_build_quality_summary_computes_missing_percentage() -> None:
    df = pd.DataFrame({"age": [25, None, 35], "name": ["a", "b", "c"]})
    metadata_result = MetadataExtractor().extract(df)
    validation_result = DatasetValidationResult(is_valid=True, issues=[])

    summary = build_quality_summary(validation_result, metadata_result)

    assert summary["is_valid"] is True
    assert summary["total_missing_values"] == 1
    assert summary["missing_value_percentage"] == round(1 / 6 * 100, 2)


def test_build_quality_summary_counts_errors_and_warnings() -> None:
    df = pd.DataFrame({"a": [1]})
    metadata_result = MetadataExtractor().extract(df)
    validation_result = DatasetValidationResult(
        is_valid=False,
        issues=[
            ValidationIssue(severity=IssueSeverity.ERROR, code="x", message="bad"),
            ValidationIssue(severity=IssueSeverity.WARNING, code="y", message="meh"),
        ],
    )

    summary = build_quality_summary(validation_result, metadata_result)

    assert summary["error_count"] == 1
    assert summary["warning_count"] == 1
