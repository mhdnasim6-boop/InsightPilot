"""ReflectionStatistics: aggregate counts/averages across every stored reflection.

Not in the phase spec's own literal ``models/`` list, but ``GET
/reflection/statistics`` needs a typed return shape — added the same way
Phase 29/30 added ``MemoryStatistics``/``CollaborationStatistics`` beyond
their own literal lists, for the identical reason.
"""

from pydantic import BaseModel, Field


class ReflectionStatistics(BaseModel):
    """Aggregate counts/averages over every stored reflection."""

    total_reflections: int = 0
    success_count: int = 0
    average_execution_score: float = 0.0
    average_efficiency_score: float = 0.0
    average_confidence_score: float = 0.0
    total_recommendations: int = 0
    by_label: dict[str, int] = Field(default_factory=dict)
