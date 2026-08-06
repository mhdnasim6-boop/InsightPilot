"""Tests for DatasetProfilingService."""

import pandas as pd

from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor


def _service(high_cardinality_ratio: float = 0.9) -> DatasetProfilingService:
    return DatasetProfilingService(MetadataExtractor(), high_cardinality_ratio=high_cardinality_ratio)


def test_profile_basic_shape_and_types() -> None:
    df = pd.DataFrame({"age": [25, 30, 35], "name": ["a", "b", "c"]})

    profile = _service().profile(df, "d1")

    assert profile.dataset_id == "d1"
    assert profile.row_count == 3
    assert profile.column_count == 2
    assert profile.data_types["age"] == str(df["age"].dtype)
    assert profile.memory_usage_bytes > 0


def test_profile_missing_value_summary() -> None:
    df = pd.DataFrame({"age": [25, None, 35], "name": ["a", "b", "c"]})

    profile = _service().profile(df, "d1")

    assert profile.missing_value_summary["total_missing"] == 1
    assert profile.missing_value_summary["missing_by_column"]["age"] == 1
    assert profile.missing_value_summary["missing_percentage"] == round(1 / 6 * 100, 2)


def test_profile_duplicate_summary() -> None:
    df = pd.DataFrame({"a": [1, 1, 2]})

    profile = _service().profile(df, "d1")

    assert profile.duplicate_summary["duplicate_row_count"] == 1
    assert profile.duplicate_summary["duplicate_percentage"] == round(1 / 3 * 100, 2)


def test_profile_splits_numeric_and_categorical_summaries() -> None:
    df = pd.DataFrame({"age": [25, 30, 35], "name": ["a", "b", "c"]})

    profile = _service().profile(df, "d1")

    assert "age" in profile.numeric_summary
    assert "age" not in profile.categorical_summary
    assert "name" in profile.categorical_summary
    assert "name" not in profile.numeric_summary


def test_profile_detects_constant_columns() -> None:
    df = pd.DataFrame({"country": ["US", "US", "US"], "amount": [1, 2, 3]})

    profile = _service().profile(df, "d1")

    assert profile.constant_columns == ["country"]


def test_profile_detects_high_cardinality_columns() -> None:
    df = pd.DataFrame({"id": ["a1", "a2", "a3", "a4"], "flag": ["x", "x", "y", "y"]})

    profile = _service(high_cardinality_ratio=0.9).profile(df, "d1")

    assert profile.high_cardinality_columns == ["id"]


def test_profile_column_statistics_matches_extractor_statistics() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})
    extractor = MetadataExtractor()
    profile = DatasetProfilingService(extractor).profile(df, "d1")

    assert profile.column_statistics == extractor.extract(df).statistics
