"""Response models for the health endpoint."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Shape of the ``GET /api/v1/health`` response."""

    status: str = Field(..., description="Overall service health.", examples=["healthy"])
    application: str = Field(..., description="Application name.", examples=["InsightPilot"])
    version: str = Field(..., description="Application version.", examples=["0.1.0"])
