"""ExecutiveSummaryResult: ExecutiveSummaryAgent's complete, structured answer
for one ExecutionStep.

The content fields mirror ``ExecutiveSummaryDraft`` exactly — this is
the domain-facing envelope around it, adding the same lifecycle fields
(``step_id``/``status``/``warnings``/``execution_time``/``metadata``)
every other agent's own result already has. ``status`` reuses
``backend.orchestration.state.state.ExecutionStatus``, same as every
other agent.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.orchestration.state.state import ExecutionStatus


class ExecutiveSummaryResult(BaseModel):
    """The complete outcome of one ExecutiveSummaryAgent run."""

    step_id: str
    status: ExecutionStatus
    executive_summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
