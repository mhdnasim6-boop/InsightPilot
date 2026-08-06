"""Data ingestion entry point.

The only object anything (a future File agent, a SQL data source, a
router, a test) should use to turn a data source into a
``BusinessDataset`` — never a ``DataLoader``, the ``LoaderRegistry``, or
pandas directly. Selects a loader, validates the source and the loaded
DataFrame, extracts metadata, stores the DataFrame for later resolution
via ``dataframe_reference``, and returns the standardized
``BusinessDataset``.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from backend.ingestion.exceptions.errors import (
    DatasetCorruptedError,
    DatasetValidationError,
)
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.metadata.quality import build_quality_summary
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType, source_type_for_extension
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.result import (
    DatasetValidationResult,
    IssueSeverity,
    ValidationIssue,
)
from backend.ingestion.validators.validator import DatasetValidator
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class IngestionService:
    """Selects a loader, validates, loads, extracts metadata, and returns a BusinessDataset."""

    def __init__(
        self,
        registry: LoaderRegistry,
        validator: DatasetValidator,
        extractor: MetadataExtractor,
        dataframe_store: DataFrameStore,
    ) -> None:
        self._registry = registry
        self._validator = validator
        self._extractor = extractor
        self._dataframe_store = dataframe_store

    def ingest(
        self,
        source_location: str,
        dataset_name: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> BusinessDataset:
        """Ingest a source file into a standardized ``BusinessDataset``.

        Raises ``DatasetValidationError`` for an unrecognized extension,
        missing/empty file, or malformed DataFrame (carrying the rich
        ``DatasetValidationResult`` as ``.detail``); ``SourceNotImplementedError``
        for a recognized-but-unimplemented source type (PDF, Word, ...).
        """
        known_extensions = self._registry.known_extensions()

        pre_check = self._validator.validate(source_location, known_extensions)
        if not pre_check.is_valid:
            raise DatasetValidationError(
                f"Dataset source failed validation: '{source_location}'.", detail=pre_check
            )

        extension = Path(source_location).suffix.lower()
        loader = self._registry.get_loader(extension)  # may raise SourceNotImplementedError

        try:
            dataframe = loader.load(source_location)
        except DatasetCorruptedError as exc:
            corrupted_result = DatasetValidationResult(
                is_valid=False,
                issues=[ValidationIssue(severity=IssueSeverity.ERROR, code="corrupted_file", message=str(exc))],
            )
            raise DatasetValidationError(
                f"Dataset source is corrupted: '{source_location}'.", detail=corrupted_result
            ) from exc

        post_check = self._validator.validate(source_location, known_extensions, dataframe=dataframe)
        if not post_check.is_valid:
            raise DatasetValidationError(f"Loaded dataset failed validation: '{source_location}'.", detail=post_check)

        source_type = source_type_for_extension(extension)
        assert source_type is not None  # known_extensions() only contains mapped extensions; narrows for mypy

        return self._build_dataset(
            dataframe,
            post_check,
            dataset_name=dataset_name or Path(source_location).stem,
            source_type=source_type,
            source_location=source_location,
            file_size=Path(source_location).stat().st_size,
            tags=tags,
            description=description,
            metadata={"loader": loader.metadata()},
        )

    def ingest_dataframe(
        self,
        dataframe: pd.DataFrame,
        dataset_name: str,
        source_type: SourceType,
        source_location: str,
        file_size: int | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BusinessDataset:
        """Wrap an already-loaded DataFrame (e.g. a SQL query result) into a ``BusinessDataset``.

        The source-independent counterpart to :meth:`ingest`: there is no
        file to check, so only ``DatasetValidator.validate_dataframe()``
        runs — metadata extraction, DataFrame storage, and
        ``BusinessDataset`` construction all proceed exactly the same way.

        Raises ``DatasetValidationError`` for a DataFrame with no columns,
        no rows, or duplicate column names (carrying the
        ``DatasetValidationResult`` as ``.detail``), exactly like
        :meth:`ingest` does for a loaded file.
        """
        post_check = self._validator.validate_dataframe(dataframe)
        if not post_check.is_valid:
            raise DatasetValidationError(f"Loaded dataset failed validation: '{source_location}'.", detail=post_check)

        return self._build_dataset(
            dataframe,
            post_check,
            dataset_name=dataset_name,
            source_type=source_type,
            source_location=source_location,
            file_size=file_size,
            tags=tags,
            description=description,
            metadata=metadata or {},
        )

    def _build_dataset(
        self,
        dataframe: pd.DataFrame,
        post_check: DatasetValidationResult,
        *,
        dataset_name: str,
        source_type: SourceType,
        source_location: str,
        file_size: int | None,
        tags: list[str] | None,
        description: str | None,
        metadata: dict[str, Any],
    ) -> BusinessDataset:
        """Extract metadata, store the DataFrame, and build the ``BusinessDataset``.

        Shared by :meth:`ingest` and :meth:`ingest_dataframe` — the only
        difference between a file-based and DataFrame-based ingestion is
        which validation ran and where ``source_type``/``source_location``/
        ``file_size`` come from; everything after that is identical.
        """
        metadata_result = self._extractor.extract(dataframe)
        quality_summary = build_quality_summary(post_check, metadata_result)

        dataset_id = generate_id()
        self._dataframe_store.put(dataset_id, dataframe)

        now = utc_now()
        return BusinessDataset(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            source_type=source_type,
            source_location=source_location,
            schema=metadata_result.column_types,
            columns=metadata_result.columns,
            row_count=metadata_result.row_count,
            column_count=metadata_result.column_count,
            file_size=file_size,
            created_at=now,
            loaded_at=now,
            dataframe_reference=dataset_id,
            sample_rows=metadata_result.sample_rows,
            statistics=metadata_result.statistics,
            quality_summary=quality_summary,
            metadata=metadata,
            tags=tags or [],
            description=description,
        )

    def get_dataframe(self, dataset: BusinessDataset) -> pd.DataFrame | None:
        """Resolve a dataset's full DataFrame via its ``dataframe_reference``.

        The one sanctioned way to get the real data behind a
        ``BusinessDataset`` — never by re-reading ``source_location``.
        """
        if dataset.dataframe_reference is None:
            return None
        return self._dataframe_store.get(dataset.dataframe_reference)
