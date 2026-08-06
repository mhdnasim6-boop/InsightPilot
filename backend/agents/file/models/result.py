"""AgentExecutionResult: FileAgent's complete, structured answer for one ExecutionStep.

Every field below is an existing model, reused as-is — never
redefined or duplicated. ``status`` reuses
``backend.orchestration.state.state.ExecutionStatus`` (the same enum
``ExecutionStep.status`` already uses), not a new agent-specific enum.
Partial-failure-tolerant by design: if cleaning fails, ``dataset`` is
still populated from the ingestion step that already succeeded —
``analysis``/``visualization``/``report`` simply stay ``None``.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.ingestion.models.dataset import BusinessDataset
from backend.orchestration.state.state import ExecutionStatus
from backend.reporting.models.report_document import ReportDocument
from backend.visualization.models.result import VisualizationResult


class AgentExecutionResult(BaseModel):
    """The complete outcome of one FileAgent run: what succeeded, what didn't, and why."""

    step_id: str
    status: ExecutionStatus
    dataset: BusinessDataset | None = None
    cleaning: CleaningOutcome | None = None
    analysis: AnalysisResult | None = None
    visualization: VisualizationResult | None = None
    report: ReportDocument | None = None
    warnings: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
