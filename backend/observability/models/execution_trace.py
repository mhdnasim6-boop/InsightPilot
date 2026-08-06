"""ExecutionTrace: the complete, immutable record of one plan's execution.

Scoped per-*plan*, not per graph-run ``execution_id`` — a plan can pause
and resume across several separate graph invocations (Phase 23's
Human-in-the-Loop), and this trace must span the plan's entire
lifecycle across however many pause/resume cycles it goes through.
``status`` reuses ``backend.planning.models.enums.PlanStatus`` directly
(the trace's status *is* the plan's status). ``approval_traces`` reuses
``ExecutionApproval`` directly — no new model, populated straight from
``ApprovalService.list_for_plan()``.

Frozen, like every other historical-record model in this codebase
(``ExecutionPlan``, ``ExecutionApproval``). ``ObservabilityService``
never mutates one in place: it holds a private mutable accumulator
while a plan runs and produces a fresh, frozen ``ExecutionTrace``
snapshot each time one is requested (mid-flight or after
``finalize_trace()``) — see the "why tracing is immutable" note in
``ObservabilityService``.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.approval.models.approval import ExecutionApproval
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.planning.models.enums import PlanStatus


class ExecutionTrace(BaseModel):
    """The complete, point-in-time-immutable record of one plan's execution."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    plan_id: str
    session_id: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    status: PlanStatus
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    approval_traces: list[ExecutionApproval] = Field(default_factory=list)
    ai_calls: list[AICallTrace] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
