"""ToolUsageAnalyzer: what tools were used, how often, and how well.

Reads only ``trace.tool_traces`` — each already carries ``tool_name``/
``status``/``duration_ms`` (``TracingTool``'s own instrumentation from
Phase 24); this module adds no new instrumentation.
"""

from typing import Any

from backend.observability.models.execution_trace import ExecutionTrace
from backend.orchestration.state.state import ExecutionStatus


def analyze_tool_usage(trace: ExecutionTrace) -> dict[str, Any]:
    """Summarize every tool call recorded in ``trace``."""
    calls_per_tool: dict[str, int] = {}
    for tool_trace in trace.tool_traces:
        calls_per_tool[tool_trace.tool_name] = calls_per_tool.get(tool_trace.tool_name, 0) + 1

    failed_tools = sorted({t.tool_name for t in trace.tool_traces if t.status == ExecutionStatus.FAILED})
    total_calls = len(trace.tool_traces)
    average_duration_ms = (sum(t.duration_ms for t in trace.tool_traces) / total_calls) if total_calls else 0.0
    slowest_tool = max(trace.tool_traces, key=lambda t: t.duration_ms).tool_name if trace.tool_traces else None

    return {
        "total_calls": total_calls,
        "unique_tools": sorted(calls_per_tool.keys()),
        "calls_per_tool": calls_per_tool,
        "failed_tools": failed_tools,
        "average_duration_ms": average_duration_ms,
        "slowest_tool": slowest_tool,
    }
