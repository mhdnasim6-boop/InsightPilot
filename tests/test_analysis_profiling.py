"""Tests for build_dataset_summary: a pure adapter over DatasetProfile."""

from backend.analysis.profiling.dataset_summary import build_dataset_summary
from backend.cleaning.models.profile import DatasetProfile
from backend.utils.time import utc_now


def test_build_dataset_summary_maps_every_field_from_the_profile() -> None:
    profile = DatasetProfile(
        dataset_id="d1",
        generated_at=utc_now(),
        row_count=10,
        column_count=3,
        memory_usage_bytes=512,
        data_types={"amount": "float64", "region": "str", "name": "str"},
        missing_value_summary={"total_missing": 2, "missing_by_column": {"amount": 2}, "missing_percentage": 6.67},
        duplicate_summary={"duplicate_row_count": 1, "duplicate_percentage": 10.0},
        numeric_summary={"amount": {"mean": 5.0}},
        categorical_summary={"region": {"unique": 2}, "name": {"unique": 10}},
    )

    summary = build_dataset_summary(profile)

    assert summary.row_count == 10
    assert summary.column_count == 3
    assert summary.numeric_columns == ["amount"]
    assert summary.categorical_columns == ["name", "region"]
    assert summary.missing_values == 2
    assert summary.memory_usage_bytes == 512
    assert summary.duplicate_count == 1
    assert summary.data_types == {"amount": "float64", "region": "str", "name": "str"}


def test_build_dataset_summary_handles_missing_optional_keys() -> None:
    profile = DatasetProfile(
        dataset_id="d1", generated_at=utc_now(), row_count=0, column_count=0, memory_usage_bytes=0
    )

    summary = build_dataset_summary(profile)

    assert summary.missing_values == 0
    assert summary.duplicate_count == 0
    assert summary.numeric_columns == []
    assert summary.categorical_columns == []
