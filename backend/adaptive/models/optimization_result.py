"""OptimizationDecision/OptimizationResult: what AdaptivePlanningService
suggests (and, where safe, applies) for one plan — and the full, auditable
record of why.

Every ``OptimizationDecision`` names the exact ``PlanningContext`` fact
that produced it (``reason``) plus how many historical data points back
it (``evidence_count``) — deterministic plan optimization, never a
black-box suggestion. Not every decision changes ``optimized_plan``:
only mechanically safe ones do (skipping a step nothing depends on,
reordering into a valid topological order); the rest (approval policy,
tool-choice, artifact reuse) are advisory, since they'd require semantic
judgment this phase deliberately keeps out of an automatic mutation.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from backend.adaptive.models.planning_context import PlanningContext
from backend.planning.models.plan import ExecutionPlan


class OptimizationDecisionCategory(str, Enum):
    """What kind of change an OptimizationDecision suggests or applies."""

    TOOL_CHOICE = "tool_choice"
    SKIP_STEP = "skip_step"
    APPROVAL_REDUCTION = "approval_reduction"
    PARALLELIZATION = "parallelization"
    REUSE_ARTIFACT = "reuse_artifact"
    REORDER = "reorder"
    OTHER = "other"


class OptimizationDecision(BaseModel):
    """One deterministic, evidence-backed suggestion (or applied change)."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    category: OptimizationDecisionCategory
    applied: bool
    message: str
    reason: str
    evidence_count: int = 0


class OptimizationResult(BaseModel):
    """One complete optimization pass: before/after plans, decisions, and the evidence behind them."""

    model_config = ConfigDict(frozen=True)

    optimization_id: str
    plan_id: str
    session_id: str | None = None
    original_plan: ExecutionPlan
    optimized_plan: ExecutionPlan
    decisions: list[OptimizationDecision] = Field(default_factory=list)
    planning_context: PlanningContext
    execution_savings_estimate_seconds: float = 0.0
    approval_savings_estimate: int = 0
    parallelism_improved: bool = False
    generated_at: datetime
