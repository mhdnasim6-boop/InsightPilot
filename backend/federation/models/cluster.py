"""Cluster: one registered InsightPilot deployment (including this process's own).

Immutable like every other lifecycle model in this codebase (`Worker`,
`ExecutionApproval`) — a state transition (health sweep, credit/release a
remote execution) produces a new instance via `model_copy`, never
in-place mutation. `active_remote_executions`/`has_capacity()`/
`load_ratio()` mirror `Worker`'s own exact shape (Phase 38) one layer up:
cluster-level credit instead of worker-level credit.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus


class Cluster(BaseModel):
    """One registered cluster: identity, capabilities, and current load."""

    model_config = ConfigDict(frozen=True)

    cluster_id: str
    name: str
    endpoint: str
    status: ClusterStatus = ClusterStatus.ONLINE
    version: str = "0.1.0"
    capabilities: ClusterCapability = Field(default_factory=ClusterCapability)
    registered_workers: int = 0
    active_remote_executions: list[str] = Field(default_factory=list)
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_local: bool = False
    registered_at: datetime | None = None
    last_seen: datetime | None = None

    def supports_agent(self, node_name: str) -> bool:
        """Whether this cluster advertises the given agent node_name as supported."""
        return node_name in self.capabilities.supported_agents

    def supports_workflow_size(self, step_count: int) -> bool:
        """Whether this cluster's own workflow-size limit accommodates ``step_count`` steps."""
        return step_count <= self.capabilities.maximum_workflow_size

    def has_capacity(self) -> bool:
        """Whether this cluster can accept one more routed workload right now."""
        return len(self.active_remote_executions) < self.capabilities.maximum_concurrent_executions

    def load_ratio(self) -> float:
        """Fraction of concurrent-execution capacity currently in use — 0.0 (idle) to 1.0 (full)."""
        return len(self.active_remote_executions) / self.capabilities.maximum_concurrent_executions
