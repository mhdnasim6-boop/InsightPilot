"""Analysis endpoint: runs every deterministic analyzer over a cleaned dataset.

A thin HTTP wrapper over the existing ``AnalysisService`` — no new
business logic. The caller sends back the ``CleaningOutcome`` it received
from ``POST /datasets/{id}/clean``; nothing about a cleaning run is
persisted server-side beyond the dataset store.
"""

from fastapi import APIRouter, Depends

from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.dependencies.analysis import get_analysis_service
from backend.schemas.response import SuccessResponse
from backend.services.analysis_service import AnalysisService

router = APIRouter()


@router.post("/analysis", response_model=SuccessResponse[AnalysisResult], summary="Analyze a cleaned dataset")
async def analyze(
    cleaning_outcome: CleaningOutcome, service: AnalysisService = Depends(get_analysis_service)
) -> SuccessResponse[AnalysisResult]:
    """Run every analyzer over ``cleaning_outcome`` and return the structured AnalysisResult."""
    result = service.analyze(cleaning_outcome)
    return SuccessResponse.ok(data=result, message="Analysis complete.")
