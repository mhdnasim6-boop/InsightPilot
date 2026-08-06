"""OptimizationStatistics: aggregate counts over every OptimizationReport ever generated.

Distinct from ``backend.adaptive.models.optimization_statistics.OptimizationStatistics``
(that one aggregates ``AdaptivePlanningService``'s own plan-optimization
history; this one aggregates *this* package's own report history) — same
class name, different module, no import collision as long as callers
import each under its own name (see ``PerformanceProfile``'s own
aliased import for the one place both are used together).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OptimizationStatistics(BaseModel):
    """Aggregate counts across every OptimizationReport this process has generated."""

    model_config = ConfigDict(frozen=True)

    total_reports: int = 0
    total_bottlenecks: int = 0
    total_actions: int = 0
    total_recommendations: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    last_analyzed_at: datetime | None = None
