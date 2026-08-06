"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.dependencies.services import get_health_service
from backend.schemas.health import HealthResponse
from backend.schemas.response import SuccessResponse
from backend.services.health_service import HealthService

router = APIRouter()


@router.get("/health", response_model=SuccessResponse[HealthResponse], summary="Service health check")
async def health_check(service: HealthService = Depends(get_health_service)) -> SuccessResponse[HealthResponse]:
    """Report whether the API is up, and which application/version is running."""
    data = service.get_health()
    return SuccessResponse.ok(data=data, message="Service is healthy.")
