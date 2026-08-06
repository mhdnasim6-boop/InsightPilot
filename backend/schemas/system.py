"""Response model for GET /api/v1/system."""

from pydantic import BaseModel

from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.orchestration.graph.metadata import GraphMetadata
from backend.schemas.health import HealthResponse


class SystemStatus(BaseModel):
    """Aggregated system status for the dashboard's System page."""

    health: HealthResponse
    ai_provider: ProviderHealth
    model_info: ModelInfo
    graph_metadata: GraphMetadata
    application_version: str
