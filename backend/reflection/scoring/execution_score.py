"""ExecutionScore: a deterministic 0-100 score for whether an execution went well.

Every score in ``backend.reflection.scoring`` shares the same shape
(``value`` + a ``breakdown`` explaining exactly which components added or
subtracted what, plus a human-readable ``label``) so a score is never a
black-box number — the breakdown is what makes it "deterministic
scoring, no AI" verifiable by inspection. ``label()`` is shared by every
scoring module in this package (imported, never duplicated).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.observability.models.execution_trace import ExecutionTrace

_STATUS_BASE = {
    "completed": 100.0,
    "paused": 60.0,
    "running": 50.0,
    "failed": 0.0,
    "cancelled": 0.0,
    "draft": 0.0,
    "validated": 0.0,
    "ready": 0.0,
}


def label_for(value: float) -> str:
    """The shared, deterministic label every score in this package uses."""
    if value >= 85.0:
        return "excellent"
    if value >= 65.0:
        return "good"
    if value >= 40.0:
        return "needs_improvement"
    return "poor"


class ExecutionScore(BaseModel):
    """How well the execution itself went: success, failures, errors, warnings."""

    model_config = ConfigDict(frozen=True)

    value: float = Field(ge=0.0, le=100.0)
    breakdown: dict[str, float] = Field(default_factory=dict)
    label: str


def compute_execution_score(trace: ExecutionTrace, execution_summary: dict[str, Any]) -> ExecutionScore:
    """Score execution health from ``trace.status`` plus failures/errors/warnings.

    ``execution_summary`` is ``execution_analyzer.analyze_execution(trace)``'s
    own output — reused, never recomputed here.
    """
    breakdown: dict[str, float] = {}
    base = _STATUS_BASE.get(trace.status.value, 50.0)
    breakdown["status_base"] = base

    failed_agents_penalty = min(40.0, len(execution_summary["failed_agents"]) * 15.0)
    breakdown["failed_agents_penalty"] = -failed_agents_penalty

    error_penalty = min(30.0, execution_summary["error_count"] * 10.0)
    breakdown["error_penalty"] = -error_penalty

    warning_penalty = min(10.0, execution_summary["warning_count"] * 2.0)
    breakdown["warning_penalty"] = -warning_penalty

    value = max(0.0, min(100.0, base - failed_agents_penalty - error_penalty - warning_penalty))
    return ExecutionScore(value=value, breakdown=breakdown, label=label_for(value))
