"""Tests for CleaningStepRecord, CleaningResult, DatasetProfile, and CleaningOutcome."""

from backend.cleaning.models.outcome import CleaningOutcome
from backend.cleaning.models.profile import DatasetProfile
from backend.cleaning.models.result import CleaningResult, CleaningStepRecord
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType
from backend.utils.time import utc_now


def test_cleaning_step_record_defaults() -> None:
    step = CleaningStepRecord(rule_name="r", description="d", rows_before=5, rows_after=5)
    assert step.columns_affected == []
    assert step.details == {}


def test_cleaning_result_defaults_and_fields() -> None:
    now = utc_now()
    result = CleaningResult(
        cleaning_id="c1",
        dataset_id="d1",
        rows_before=10,
        rows_after=8,
        columns_before=3,
        columns_after=3,
        missing_values_before=4,
        missing_values_after=0,
        duplicates_removed=2,
        summary="ok",
        quality_score=100.0,
        created_at=now,
    )
    assert result.steps_applied == []
    assert result.warnings == []
    assert result.columns_modified == []
    assert result.metadata == {}
    assert result.quality_score == 100.0


def test_dataset_profile_defaults_and_fields() -> None:
    profile = DatasetProfile(
        dataset_id="d1",
        generated_at=utc_now(),
        row_count=10,
        column_count=3,
        memory_usage_bytes=1234,
    )
    assert profile.data_types == {}
    assert profile.constant_columns == []
    assert profile.high_cardinality_columns == []
    assert profile.metadata == {}


def test_cleaning_outcome_bundles_all_three() -> None:
    now = utc_now()
    dataset = BusinessDataset(
        dataset_id="d1",
        dataset_name="sales",
        source_type=SourceType.CSV,
        source_location="/data/sales.csv",
        row_count=1,
        column_count=1,
        created_at=now,
        loaded_at=now,
    )
    result = CleaningResult(
        cleaning_id="c1",
        dataset_id="d1",
        rows_before=1,
        rows_after=1,
        columns_before=1,
        columns_after=1,
        missing_values_before=0,
        missing_values_after=0,
        duplicates_removed=0,
        summary="ok",
        quality_score=100.0,
        created_at=now,
    )
    profile = DatasetProfile(dataset_id="d1", generated_at=now, row_count=1, column_count=1, memory_usage_bytes=1)

    outcome = CleaningOutcome(dataset=dataset, result=result, profile=profile)

    assert outcome.dataset.dataset_id == "d1"
    assert outcome.result.cleaning_id == "c1"
    assert outcome.profile.row_count == 1
