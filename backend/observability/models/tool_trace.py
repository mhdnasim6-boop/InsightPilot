"""ToolTrace: one tool call's recorded execution, captured by TracingTool.

Unlike agent-level tracing, tool-level tracing has no existing
instrumentation to reuse — no tool call currently emits any event or
result of its own, it either returns a value or raises. ``TracingTool``
(``backend.observability.services.tracing_tool``) is the one new
instrumentation point this phase adds, wrapping every DI-provided tool
so every call through it produces one ``ToolTrace``, timing it and
capturing the wrapped tool's own ``input_schema()``/``output_schema()``
(already built in the Tool Layer — Phase 22). ``agent_name`` is plumbing,
not part of the task's own field list, but necessary to attribute a
tool call back to the agent that made it (via
``backend.observability.context.current_agent_name``), the same way a
child span records its parent in any distributed tracing system.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.orchestration.state.state import ExecutionStatus


class ToolTrace(BaseModel):
    """One tool invocation's recorded execution within a trace."""

    model_config = ConfigDict(frozen=True)

    tool_name: str
    agent_name: str | None = None
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: ExecutionStatus
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
