"""FederationStatistics: a point-in-time aggregate view of the whole cluster fleet."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FederationStatistics(BaseModel):
    """Aggregate counts across every registered cluster and its routing/execution state."""

    model_config = ConfigDict(frozen=True)

    total_clusters: int = 0
    online_clusters: int = 0
    degraded_clusters: int = 0
    offline_clusters: int = 0
    maintenance_clusters: int = 0
    failed_clusters: int = 0
    total_registered_workers: int = 0
    total_capacity: int = 0
    active_remote_executions: int = 0
    pending_routing_decisions: int = 0
    generated_at: datetime
