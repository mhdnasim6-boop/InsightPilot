"""The raw, LLM-facing shape the parser validates before anything becomes the
real ``ExecutiveSummaryResult``.

Mirrors ``backend.agents.planner.models.draft.PlannerPlanDraft``: the LLM
can only ever populate these fields — never execution-state fields like
``step_id``/``status``/``warnings``/``execution_time``, which
``ExecutiveSummaryAgent`` always sets itself. ``confidence`` is bounded
at the schema level, so an out-of-range value is rejected by pydantic
during parsing, not by hand-written validation.
"""

from pydantic import BaseModel, Field


class ExecutiveSummaryDraft(BaseModel):
    """The executive summary content exactly as the LLM is allowed to describe it."""

    executive_summary: str
    key_findings: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
