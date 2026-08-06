"""BrowserAgentResult: BrowserAgent's complete, structured answer for one ExecutionStep.

``sources``/``summaries`` reuse ``SourceResult``/``SearchOutcome`` from
``backend.browser.models`` directly, never redefined — the same reuse
relationship ``AgentExecutionResult`` has with ``BusinessDataset``/
``AnalysisResult``/etc. ``status`` reuses
``backend.orchestration.state.state.ExecutionStatus`` too, including its
``SKIPPED`` value: a step with no search-relevant input is not a
failure, so it is reported as SKIPPED, never FAILED.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.browser.models.context import SearchOutcome, SourceResult
from backend.orchestration.state.state import ExecutionStatus


class BrowserAgentResult(BaseModel):
    """The complete outcome of one BrowserAgent run: what it searched for, and what it found."""

    step_id: str
    status: ExecutionStatus
    sources: list[SourceResult] = Field(default_factory=list)
    summaries: list[SearchOutcome] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
