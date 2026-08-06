"""TracingTool: a transparent Tool decorator that records a ToolTrace for every call.

Wired into each ``get_X_tool()`` DI provider (``backend.dependencies.tools``)
so every tool call is traced with zero changes to the 5 agents that call
tools or the concrete tool implementations themselves — mirrors the
``_SpyTool`` test helper already used in
``tests/test_agents_use_tools.py`` (Phase 22), but production-grade:
real timing, real correlation via
``backend.observability.context``, and delegation to an optional
``ObservabilityService`` rather than a plain list.

Never swallows an exception — a Tool's own contract
(``backend.tools.base.tool``) is that ``execute()`` raises whatever the
wrapped call raises; this class records a FAILED ``ToolTrace`` and then
re-raises, same as the wrapped tool would have on its own.
"""

import time
from datetime import datetime
from typing import Any

from backend.observability.context import current_agent_name, current_trace_id
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.state.state import ExecutionStatus
from backend.tools.base.tool import Tool
from backend.utils.time import utc_now


class TracingTool(Tool[Any, Any]):
    """Wraps a real tool, recording a ToolTrace for every call before delegating."""

    def __init__(self, inner: Tool[Any, Any], observability_service: ObservabilityService | None = None) -> None:
        self._inner = inner
        self._observability_service = observability_service
        self.name = inner.name
        self.description = inner.description
        self.input_model = inner.input_model
        self.output_model = inner.output_model

    async def execute(self, tool_input: Any) -> Any:
        if self._observability_service is None or current_trace_id.get() is None:
            return await self._inner.execute(tool_input)

        start_time = utc_now()
        start = time.perf_counter()
        try:
            result = await self._inner.execute(tool_input)
        except Exception as exc:
            self._record(start_time, start, ExecutionStatus.FAILED, error=str(exc))
            raise
        self._record(start_time, start, ExecutionStatus.COMPLETED)
        return result

    def input_schema(self) -> dict[str, Any]:
        return self._inner.input_schema()

    def output_schema(self) -> dict[str, Any]:
        return self._inner.output_schema()

    def _record(self, start_time: datetime, start: float, status: ExecutionStatus, error: str | None = None) -> None:
        if self._observability_service is None:
            return
        end_time = utc_now()
        self._observability_service.record_tool_trace(
            ToolTrace(
                tool_name=self.name,
                agent_name=current_agent_name.get(),
                start_time=start_time,
                end_time=end_time,
                duration_ms=(time.perf_counter() - start) * 1000,
                status=status,
                input_schema=self.input_schema(),
                output_schema=self.output_schema(),
                error=error,
            )
        )
