"""ReportAgentResult: ReportAgent's complete, structured answer for one ExecutionStep.

``report_document`` reuses ``ReportDocument`` directly from
``backend.reporting.models.report_document`` — never redefined — the
same reuse relationship ``AgentExecutionResult`` has with
``BusinessDataset``/``AnalysisResult``. ``status`` reuses
``backend.orchestration.state.state.ExecutionStatus``, same as every
other agent.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.orchestration.state.state import ExecutionStatus
from backend.reporting.models.report_document import ReportDocument


class ReportAgentResult(BaseModel):
    """The complete outcome of one ReportAgent run: the report it built, or why it couldn't."""

    step_id: str
    status: ExecutionStatus
    report_id: str | None = None
    report_document: ReportDocument | None = None
    warnings: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
