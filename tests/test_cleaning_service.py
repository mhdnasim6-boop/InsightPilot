"""Integration tests for CleaningService: clean a real ingested dataset, preserving the original."""

from pathlib import Path

import pytest

from backend.cleaning.exceptions.errors import DataFrameNotFoundError
from backend.cleaning.pipeline.pipeline import CleaningPipeline
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.cleaning.rules.duplicate_row_rule import DuplicateRowRule
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService


def _make_services() -> tuple[IngestionService, CleaningService, DataFrameStore]:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    profiling_service = DatasetProfilingService(extractor)
    cleaning_service = CleaningService(ingestion_service, profiling_service, extractor, dataframe_store)
    return ingestion_service, cleaning_service, dataframe_store


def test_clean_produces_a_new_dataset_id_and_preserves_the_original(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(" Region ,Amount\nEast ,100\n West,200\nEast ,100\nEast ,\n")
    ingestion_service, cleaning_service, _ = _make_services()

    original_dataset = ingestion_service.ingest(str(csv_file))
    original_dataframe = ingestion_service.get_dataframe(original_dataset)
    assert original_dataframe is not None
    original_dataframe_snapshot = original_dataframe.copy(deep=True)

    outcome = cleaning_service.clean(original_dataset)

    assert outcome.dataset.dataset_id != original_dataset.dataset_id
    assert outcome.dataset.dataframe_reference == outcome.dataset.dataset_id

    # The original dataset object's own fields are untouched.
    assert original_dataset.row_count == 4
    assert list(original_dataset.schema) == [" Region ", "Amount"]

    # The original DataFrame in the store is untouched (immutability guarantee).
    still_stored_original = ingestion_service.get_dataframe(original_dataset)
    assert still_stored_original is not None
    assert still_stored_original.equals(original_dataframe_snapshot)


def test_clean_result_reflects_the_default_pipeline_effects(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(" Region ,Amount\nEast ,100\n West,200\nEast ,100\nEast ,\n")
    ingestion_service, cleaning_service, _ = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))

    outcome = cleaning_service.clean(dataset)

    assert outcome.result.dataset_id == dataset.dataset_id
    assert outcome.result.duplicates_removed == 1
    assert outcome.result.rows_after == 2  # 4 rows -> drop 1 missing -> drop 1 duplicate
    assert "region" in outcome.dataset.schema
    assert outcome.result.metadata["cleaned_dataset_id"] == outcome.dataset.dataset_id


def test_clean_profile_describes_the_cleaned_dataframe(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\nWest,200\n")
    ingestion_service, cleaning_service, _ = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))

    outcome = cleaning_service.clean(dataset)

    assert outcome.profile.dataset_id == dataset.dataset_id
    assert outcome.profile.row_count == outcome.dataset.row_count


def test_clean_supports_a_custom_pipeline(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\nEast,100\n")
    ingestion_service, cleaning_service, _ = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))

    custom_pipeline = CleaningPipeline([DuplicateRowRule()])
    outcome = cleaning_service.clean(dataset, pipeline=custom_pipeline)

    assert [step.rule_name for step in outcome.result.steps_applied] == ["duplicate_row_rule"]
    assert outcome.result.rows_after == 1


def test_clean_raises_dataframe_not_found_for_a_dataset_with_no_stored_dataframe(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\n")
    ingestion_service, cleaning_service, dataframe_store = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))

    dataframe_store.delete(dataset.dataset_id)

    with pytest.raises(DataFrameNotFoundError):
        cleaning_service.clean(dataset)


def test_cleaned_dataset_records_a_relationship_to_the_original(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\n")
    ingestion_service, cleaning_service, _ = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))

    outcome = cleaning_service.clean(dataset)

    assert outcome.dataset.relationships == [dataset.dataset_id]
    assert outcome.dataset.metadata["derived_from_dataset_id"] == dataset.dataset_id
