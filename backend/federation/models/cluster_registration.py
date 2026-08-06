"""ClusterRegistration: one recorded registration event, kept for audit history.

Mirrors `WorkerHeartbeat`'s own role in Phase 38 — a bounded, append-only
history entry, not the live `Cluster` state itself (`ClusterRegistry`'s
own store is that).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClusterRegistration(BaseModel):
    """One registration (or re-registration) event for a cluster."""

    model_config = ConfigDict(frozen=True)

    registration_id: str
    cluster_id: str
    name: str
    endpoint: str
    registered_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
