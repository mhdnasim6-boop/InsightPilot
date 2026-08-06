"""PlanningContext: the deterministic, structured historical evidence one
AdaptivePlanningService.optimize()/.explain() call gathers before reasoning
about a plan.

Every sub-dict here is a specific analyzer's own output (plain dicts,
mirroring ``ExecutionReview.tool_summary``'s own "return what was
computed, no extra model" precedent from Phase 31) — never raw
``ReflectionResult``/``MemoryItem`` objects, so a ``PlanningContext`` stays
small and JSON-friendly even after hundreds of prior executions.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanningContext(BaseModel):
    """The gathered historical evidence behind one optimization pass."""

    model_config = ConfigDict(frozen=True)

    session_id: str | None = None
    goal: str | None = None
    reflection_patterns: dict[str, Any] = Field(default_factory=dict)
    execution_patterns: dict[str, Any] = Field(default_factory=dict)
    collaboration_patterns: dict[str, Any] = Field(default_factory=dict)
    tool_patterns: dict[str, Any] = Field(default_factory=dict)
