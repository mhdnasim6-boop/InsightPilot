"""AgentTrace: one orchestration node's (agent's) contribution to an ExecutionTrace.

Built entirely from data every agent already produces — no new
instrumentation. Every agent result model (``AgentExecutionResult``,
``BrowserAgentResult``, ``ReportAgentResult``, ``ExecutiveSummaryResult``,
``PlannerAgentResult``) already carries ``step_id``/``status``/
``warnings``/``execution_time``/``metadata``; ``ObservabilityService``
builds one ``AgentTrace`` per ``state.artifacts`` entry ending in
``_result`` after a step settles. ``status`` reuses
``backend.orchestration.state.state.ExecutionStatus`` directly — the
same enum every agent result already uses, not a new tracing-specific
enum.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.orchestration.state.state import ExecutionStatus


class AgentTrace(BaseModel):
    """One agent's (orchestration node's) recorded execution within a trace."""

    model_config = ConfigDict(frozen=True)

    agent_name: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: ExecutionStatus
    input_size: int
    output_size: int
    tool_calls: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
