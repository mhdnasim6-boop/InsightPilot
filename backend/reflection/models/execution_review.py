"""ExecutionReview: the complete analytical output of reflecting on one execution.

Every field is produced by a specific, deterministic analyzer/scorer in
``backend.reflection`` — nothing here is free text from an AI call.
``tool_summary``/``approval_summary``/``collaboration_summary``/
``memory_summary`` are plain dicts (the exact shape each analyzer
returns), mirroring ``CollaborationService.history()``'s own
"return what was computed, no extra model" precedent — a dedicated
model per summary would just restate the analyzer's own return shape.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.reflection.models.improvement import Improvement
from backend.reflection.models.recommendation import Recommendation
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore
from backend.reflection.scoring.execution_score import ExecutionScore


class ExecutionReview(BaseModel):
    """What happened, what succeeded/failed/was slow, and what to do differently next time."""

    model_config = ConfigDict(frozen=True)

    overall_success: bool
    execution_score: ExecutionScore
    efficiency_score: EfficiencyScore
    confidence_score: ConfidenceScore
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    tool_summary: dict[str, Any] = Field(default_factory=dict)
    approval_summary: dict[str, Any] = Field(default_factory=dict)
    collaboration_summary: dict[str, Any] = Field(default_factory=dict)
    memory_summary: dict[str, Any] = Field(default_factory=dict)
    future_improvements: list[Improvement] = Field(default_factory=list)
