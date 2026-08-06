"""WorkflowStatistics: derived, read-only aggregate counts over every
known Workflow/WorkflowExecution — recomputed fresh on every request,
never stored, mirroring ``MemoryStatistics``/``ExecutionMetricsSummary``.
"""

from pydantic import BaseModel, Field


class WorkflowStatistics(BaseModel):
    """Aggregate counts over every workflow and execution the WorkflowStore currently holds."""

    total_workflows: int = 0
    total_executions: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    successful_executions: int = 0
    failed_executions: int = 0
    average_duration_seconds: float = 0.0
