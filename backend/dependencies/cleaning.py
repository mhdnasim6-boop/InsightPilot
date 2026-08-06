"""Cleaning providers: profiling service, cleaning service."""

from functools import lru_cache

from fastapi import Depends

from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.dependencies.ingestion import (
    get_dataframe_store,
    get_ingestion_service,
    get_metadata_extractor,
)
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService


@lru_cache
def get_dataset_profiling_service(
    extractor: MetadataExtractor = Depends(get_metadata_extractor),
) -> DatasetProfilingService:
    """Return the process-wide DatasetProfilingService singleton (stateless, safe to share)."""
    return DatasetProfilingService(extractor)


def get_cleaning_service(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    profiling_service: DatasetProfilingService = Depends(get_dataset_profiling_service),
    extractor: MetadataExtractor = Depends(get_metadata_extractor),
    dataframe_store: DataFrameStore = Depends(get_dataframe_store),
) -> CleaningService:
    """Provide the CleaningService — the only object that should be used for data cleaning."""
    return CleaningService(ingestion_service, profiling_service, extractor, dataframe_store)
