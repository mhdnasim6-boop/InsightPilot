"""OptimizationStatistics: aggregate counts/averages across every stored
optimization — mirrors ReflectionStatistics/CollaborationStatistics's own
"aggregate snapshot, never persisted itself" shape.
"""

from pydantic import BaseModel, Field


class OptimizationStatistics(BaseModel):
    """Aggregate counts/averages over every stored OptimizationResult."""

    total_optimizations: int = 0
    total_decisions: int = 0
    applied_decision_count: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    average_decisions_per_optimization: float = 0.0
    total_estimated_execution_savings_seconds: float = 0.0
    total_estimated_approval_savings: int = 0
