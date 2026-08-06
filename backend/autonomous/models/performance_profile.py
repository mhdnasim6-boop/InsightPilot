"""PerformanceProfile: a point-in-time snapshot of platform-wide statistics.

Every field embeds an already-existing statistics model from the
service it was computed by, verbatim — never a re-derived or duplicated
copy. This is the literal enforcement of "never duplicate analytics
already available": ``AutonomousService`` fetches each of these from its
own owning service's real `.statistics()`/`.summary()` call and hands
them here unchanged.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.adaptive.models.optimization_statistics import (
    OptimizationStatistics as AdaptiveOptimizationStatistics,
)
from backend.distributed.models.cluster_statistics import (
    ClusterStatistics as WorkerFleetStatistics,
)
from backend.federation.models.federation_statistics import FederationStatistics
from backend.memory.models.memory_statistics import MemoryStatistics
from backend.observability.metrics.models import ExecutionMetricsSummary
from backend.reflection.models.reflection_statistics import ReflectionStatistics
from backend.workflows.models.workflow_statistics import WorkflowStatistics


class PerformanceProfile(BaseModel):
    """Every reused service's own current statistics, gathered at one point in time."""

    model_config = ConfigDict(frozen=True)

    execution_metrics: ExecutionMetricsSummary = Field(default_factory=ExecutionMetricsSummary)
    workflow_statistics: WorkflowStatistics = Field(default_factory=WorkflowStatistics)
    worker_fleet_statistics: WorkerFleetStatistics
    federation_statistics: FederationStatistics
    memory_statistics: MemoryStatistics = Field(default_factory=MemoryStatistics)
    reflection_statistics: ReflectionStatistics = Field(default_factory=ReflectionStatistics)
    adaptive_optimization_statistics: AdaptiveOptimizationStatistics = Field(
        default_factory=AdaptiveOptimizationStatistics
    )
    recent_failure_event_count: int = 0
    audit_event_count: int = 0
    generated_at: datetime
