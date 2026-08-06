"""Dataset endpoints: upload+ingest, listing, fetching, and cleaning.

Thin HTTP wrappers over existing services — ``FileService`` (Phase 2,
its first real caller), ``IngestionService``, and ``CleaningService``.
The only genuinely new logic here is writing the uploaded bytes to the
path ``FileService``/``build_upload_path`` already compute — Phase 2
deliberately stopped short of that ("no file content is ever read or
written here — that's out of scope for this phase").
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.cleaning.models.outcome import CleaningOutcome
from backend.core.exceptions import NotFoundError
from backend.dependencies.cleaning import get_cleaning_service
from backend.dependencies.ingestion import (
    get_business_dataset_store,
    get_ingestion_service,
)
from backend.dependencies.services import get_file_service
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.schemas.response import SuccessResponse
from backend.services.cleaning_service import CleaningService
from backend.services.file_service import FileService
from backend.services.ingestion_service import IngestionService

router = APIRouter()


@router.post(
    "/datasets/upload",
    response_model=SuccessResponse[BusinessDataset],
    summary="Upload a CSV/Excel file and ingest it into a BusinessDataset",
)
async def upload_dataset(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
) -> SuccessResponse[BusinessDataset]:
    """Register, save, and ingest an uploaded file in one request."""
    original_filename = file.filename or "upload"
    metadata = file_service.register_file(
        session_id=session_id,
        original_filename=original_filename,
        content_type=file.content_type,
        size_bytes=file.size,
    )

    storage_path = Path(metadata.storage_path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(await file.read())

    dataset = ingestion_service.ingest(str(storage_path), dataset_name=original_filename)
    dataset_store.put(dataset)

    return SuccessResponse.ok(data=dataset, message=f"Dataset '{original_filename}' ingested.")


@router.get("/datasets", response_model=SuccessResponse[list[BusinessDataset]], summary="List ingested datasets")
async def list_datasets(
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
) -> SuccessResponse[list[BusinessDataset]]:
    """Return every dataset ingested (or cleaned) so far, most recently added first."""
    return SuccessResponse.ok(data=dataset_store.list(), message="Datasets fetched.")


@router.get("/datasets/{dataset_id}", response_model=SuccessResponse[BusinessDataset], summary="Fetch one dataset")
async def get_dataset(
    dataset_id: str, dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store)
) -> SuccessResponse[BusinessDataset]:
    """Fetch a single dataset by ID. Raises NotFoundError (404) if it doesn't exist."""
    dataset = dataset_store.get(dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset '{dataset_id}' was not found.")
    return SuccessResponse.ok(data=dataset, message="Dataset fetched.")


@router.post(
    "/datasets/{dataset_id}/clean",
    response_model=SuccessResponse[CleaningOutcome],
    summary="Run the default cleaning pipeline on a dataset",
)
async def clean_dataset(
    dataset_id: str,
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
    cleaning_service: CleaningService = Depends(get_cleaning_service),
) -> SuccessResponse[CleaningOutcome]:
    """Clean a previously ingested dataset. The cleaned result is also stored, for selection later."""
    dataset = dataset_store.get(dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset '{dataset_id}' was not found.")

    outcome = cleaning_service.clean(dataset)
    dataset_store.put(outcome.dataset)

    return SuccessResponse.ok(data=outcome, message="Dataset cleaned.")
