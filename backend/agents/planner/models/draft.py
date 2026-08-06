"""The raw, LLM-facing shape the parser validates before anything becomes a
real domain model.

Deliberately narrow: the LLM can only ever populate these fields — never
execution-state fields like ``status``/``retry_policy``/``outputs`` on the
real ``ExecutionStep``, which ``PlannerService`` always sets itself. This
is what makes "the Planner must never execute business logic" true at the
schema level, not just by convention.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.planner.models.complexity import ComplexityLevel


class PlannerStepDraft(BaseModel):
    """One step as the LLM is allowed to describe it.

    ``inputs`` is only ever populated by the Planner for *source* steps
    (FileAgent/SQLAgent/BrowserAgent) whose raw inputs are knowable at
    planning time (a dataset reference, a SQL table, search topics).
    Dependent steps (ReportAgent/ExecutiveSummaryAgent) structurally
    cannot have their real inputs known yet — those are resolved
    automatically from ``state.artifacts`` at execution time by their
    own orchestration node — so the Planner leaves their ``inputs``
    empty; getting agent selection/order/dependencies right is its job,
    not fully specifying downstream data wiring.
    """

    step_id: str
    name: str
    description: str | None = None
    node_name: str
    dependencies: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)


class PlannerPlanDraft(BaseModel):
    """The full plan as the LLM is allowed to describe it.

    ``estimated_complexity`` is typed as the closed ``ComplexityLevel``
    enum (not ``str``) so an out-of-vocabulary value is rejected by
    pydantic itself during parsing — one less thing ``PlanParser`` has to
    check by hand.
    """

    goal: str
    reasoning_summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    estimated_complexity: ComplexityLevel
    estimated_duration: float | None = None
    steps: list[PlannerStepDraft] = Field(default_factory=list)
