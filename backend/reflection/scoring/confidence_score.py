"""ConfidenceScore: a deterministic 0-100 score for how much to trust this
execution's outcome — success plus corroborating evidence (relevant prior
memory, clean collaboration) raise it; warnings/errors lower it.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.reflection.scoring.execution_score import label_for


class ConfidenceScore(BaseModel):
    """How much confidence this execution's outcome deserves."""

    model_config = ConfigDict(frozen=True)

    value: float = Field(ge=0.0, le=100.0)
    breakdown: dict[str, float] = Field(default_factory=dict)
    label: str


def compute_confidence_score(
    execution_summary: dict[str, Any], memory_summary: dict[str, Any], collaboration_summary: dict[str, Any]
) -> ConfidenceScore:
    """Score confidence from success, warnings/errors, and corroborating memory/collaboration evidence.

    All three inputs are other analyzers' own output — reused, never
    recomputed here.
    """
    breakdown: dict[str, float] = {}

    base = 80.0 if execution_summary["overall_success"] else 30.0
    breakdown["base"] = base

    warning_penalty = min(20.0, execution_summary["warning_count"] * 3.0)
    breakdown["warning_penalty"] = -warning_penalty

    error_penalty = min(30.0, execution_summary["error_count"] * 10.0)
    breakdown["error_penalty"] = -error_penalty

    memory_bonus = 10.0 if memory_summary["reused_memory"] else 0.0
    breakdown["memory_reuse_bonus"] = memory_bonus

    collaboration_bonus = (
        5.0 if collaboration_summary["used_collaboration"] and collaboration_summary["failed_subtasks"] == 0 else 0.0
    )
    breakdown["collaboration_bonus"] = collaboration_bonus

    value = max(0.0, min(100.0, base - warning_penalty - error_penalty + memory_bonus + collaboration_bonus))
    return ConfidenceScore(value=value, breakdown=breakdown, label=label_for(value))
