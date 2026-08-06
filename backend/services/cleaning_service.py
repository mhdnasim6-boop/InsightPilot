"""Data cleaning entry point.

The only object anything (a future Analysis agent, a router, a test)
should use to clean a BusinessDataset — never CleaningPipeline,
CleaningRule, or DatasetProfilingService directly. Retrieves the
dataset's DataFrame via IngestionService, runs a CleaningPipeline against
a deep copy of it (the original DataFrame and BusinessDataset are never
mutated), profiles the result, stores it as a new dataset ID, and returns
the cleaned BusinessDataset alongside the CleaningResult and DatasetProfile
that describe what happened.
"""

from backend.cleaning.exceptions.errors import DataFrameNotFoundError
from backend.cleaning.models.outcome import CleaningOutcome
from backend.cleaning.pipeline.default_pipeline import build_default_pipeline
from backend.cleaning.pipeline.pipeline import CleaningPipeline
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.services.ingestion_service import IngestionService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class CleaningService:
    """Cleans a BusinessDataset, producing a new dataset while preserving the original."""

    def __init__(
        self,
        ingestion_service: IngestionService,
        profiling_service: DatasetProfilingService,
        extractor: MetadataExtractor,
        dataframe_store: DataFrameStore,
    ) -> None:
        self._ingestion_service = ingestion_service
        self._profiling_service = profiling_service
        self._extractor = extractor
        self._dataframe_store = dataframe_store

    def clean(self, dataset: BusinessDataset, pipeline: CleaningPipeline | None = None) -> CleaningOutcome:
        """Clean ``dataset`` and return the cleaned BusinessDataset, CleaningResult, and DatasetProfile.

        The original dataset and its DataFrame are never modified —
        cleaning always runs against a deep copy and is stored under a
        brand new dataset ID, leaving ``dataset.dataframe_reference``
        resolvable to the untouched original.
        """
        original_dataframe = self._ingestion_service.get_dataframe(dataset)
        if original_dataframe is None:
            raise DataFrameNotFoundError(f"No DataFrame found for dataset '{dataset.dataset_id}'; cannot clean.")

        working_dataframe = original_dataframe.copy(deep=True)
        active_pipeline = pipeline or build_default_pipeline()
        cleaned_dataframe, cleaning_result = active_pipeline.execute(working_dataframe, dataset.dataset_id)

        profile = self._profiling_service.profile(cleaned_dataframe, dataset.dataset_id)

        new_dataset_id = generate_id()
        self._dataframe_store.put(new_dataset_id, cleaned_dataframe)
        cleaning_result = cleaning_result.model_copy(
            update={"metadata": {**cleaning_result.metadata, "cleaned_dataset_id": new_dataset_id}}
        )

        metadata_result = self._extractor.extract(cleaned_dataframe)
        now = utc_now()
        cleaned_dataset = BusinessDataset(
            dataset_id=new_dataset_id,
            dataset_name=dataset.dataset_name,
            source_type=dataset.source_type,
            source_location=dataset.source_location,
            schema=metadata_result.column_types,
            columns=metadata_result.columns,
            row_count=metadata_result.row_count,
            column_count=metadata_result.column_count,
            # No file backs a cleaned, in-memory-only dataset — its real
            # footprint is `profile.memory_usage_bytes`, not a file size.
            file_size=None,
            created_at=now,
            loaded_at=now,
            dataframe_reference=new_dataset_id,
            sample_rows=metadata_result.sample_rows,
            statistics=metadata_result.statistics,
            quality_summary={
                "is_valid": len(cleaning_result.warnings) == 0,
                "total_missing_values": cleaning_result.missing_values_after,
                "quality_score": cleaning_result.quality_score,
            },
            metadata={
                **dataset.metadata,
                "derived_from_dataset_id": dataset.dataset_id,
                "cleaning_id": cleaning_result.cleaning_id,
            },
            relationships=[dataset.dataset_id],
            tags=dataset.tags,
            description=dataset.description,
        )

        return CleaningOutcome(dataset=cleaned_dataset, result=cleaning_result, profile=profile)
