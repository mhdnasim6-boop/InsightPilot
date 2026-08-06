"""The bundle CleaningService returns: the cleaned dataset plus its report and profile."""

from pydantic import BaseModel

from backend.cleaning.models.profile import DatasetProfile
from backend.cleaning.models.result import CleaningResult
from backend.ingestion.models.dataset import BusinessDataset


class CleaningOutcome(BaseModel):
    """Everything ``CleaningService.clean()`` produces from one cleaning run."""

    dataset: BusinessDataset
    result: CleaningResult
    profile: DatasetProfile
