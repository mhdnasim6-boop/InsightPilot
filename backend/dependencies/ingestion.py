"""Ingestion providers: registry, validator, extractor, dataframe store, ingestion service."""

from functools import lru_cache

from fastapi import Depends

from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.services.ingestion_service import IngestionService


@lru_cache
def get_dataframe_store() -> DataFrameStore:
    """Return the process-wide DataFrame store singleton.

    Cached like JobManager/DataFrameStore's callers need: a DataFrame
    ingested in one request must still be resolvable via
    ``dataframe_reference`` in a later one.
    """
    return DataFrameStore()


@lru_cache
def get_business_dataset_store() -> BusinessDatasetStore:
    """Return the process-wide BusinessDataset store singleton.

    Cached for the same reason as ``get_dataframe_store``: datasets
    registered by the upload/clean endpoints must still be listable
    (for the dashboard's dataset selector) in later requests.
    """
    return BusinessDatasetStore()


@lru_cache
def get_loader_registry() -> LoaderRegistry:
    """Return the process-wide LoaderRegistry singleton (stateless, safe to share)."""
    return LoaderRegistry()


@lru_cache
def get_dataset_validator() -> DatasetValidator:
    """Return the process-wide DatasetValidator singleton (stateless, safe to share)."""
    return DatasetValidator()


@lru_cache
def get_metadata_extractor() -> MetadataExtractor:
    """Return the process-wide MetadataExtractor singleton (stateless, safe to share)."""
    return MetadataExtractor()


def get_ingestion_service(
    registry: LoaderRegistry = Depends(get_loader_registry),
    validator: DatasetValidator = Depends(get_dataset_validator),
    extractor: MetadataExtractor = Depends(get_metadata_extractor),
    dataframe_store: DataFrameStore = Depends(get_dataframe_store),
) -> IngestionService:
    """Provide the IngestionService — the only object that should be used for data ingestion."""
    return IngestionService(registry, validator, extractor, dataframe_store)
