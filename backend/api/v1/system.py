"""System status endpoint: aggregates health, AI provider, and orchestration
graph status for the dashboard's System page.

A thin HTTP wrapper aggregating existing services — no new business logic.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.ai import get_ai_service
from backend.dependencies.orchestration import get_orchestration_service
from backend.dependencies.services import get_health_service
from backend.schemas.response import SuccessResponse
from backend.schemas.system import SystemStatus
from backend.services.ai_service import AIService
from backend.services.health_service import HealthService
from backend.services.orchestration_service import OrchestrationService
from config.settings import Settings, get_settings

router = APIRouter()


@router.get("/system", response_model=SuccessResponse[SystemStatus], summary="Aggregated system status")
async def get_system_status(
    health_service: HealthService = Depends(get_health_service),
    ai_service: AIService = Depends(get_ai_service),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
    settings: Settings = Depends(get_settings),
) -> SuccessResponse[SystemStatus]:
    """Aggregate health, AI provider, and orchestration graph status into one response."""
    health = health_service.get_health()
    ai_health = await ai_service.health_check()
    model_info = await ai_service.get_model_info()
    graph_metadata = orchestration_service.get_graph_metadata()

    status = SystemStatus(
        health=health,
        ai_provider=ai_health,
        model_info=model_info,
        graph_metadata=graph_metadata,
        application_version=settings.app_version,
    )
    return SuccessResponse.ok(data=status, message="System status fetched.")
