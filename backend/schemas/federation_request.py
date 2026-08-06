"""Request models for /api/v1/federation.

Mirrors every other phase's own ``backend/schemas/*_request.py`` module —
REST-only shapes, distinct from the federation domain's own
``backend/federation/models/``.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.federation.models.cluster_capability import ClusterCapability


class RegisterClusterRequest(BaseModel):
    """Body for POST /federation/clusters/register."""

    cluster_id: str
    name: str
    endpoint: str
    capabilities: ClusterCapability = Field(default_factory=ClusterCapability)
    version: str = "0.1.0"
    registered_workers: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemoveClusterRequest(BaseModel):
    """Body for POST /federation/clusters/remove."""

    cluster_id: str
