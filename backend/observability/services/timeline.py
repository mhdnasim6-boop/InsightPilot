"""build_timeline(): merges one ExecutionTrace's agent/tool/AI/approval
records into a single chronological Execution Timeline.

A pure function, not a service — a timeline is nothing but a
sort-and-reshape of data an ``ExecutionTrace`` already has; there is no
state to own.
"""

from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.timeline import TimelineEntry


def build_timeline(trace: ExecutionTrace) -> list[TimelineEntry]:
    """Return every agent/tool/AI-call/approval record in ``trace``, oldest first."""
    entries = [
        TimelineEntry(
            kind="agent",
            name=agent_trace.agent_name,
            start_time=agent_trace.start_time,
            end_time=agent_trace.end_time,
            duration_ms=agent_trace.duration_ms,
            status=agent_trace.status.value,
        )
        for agent_trace in trace.agent_traces
    ]
    entries += [
        TimelineEntry(
            kind="tool",
            name=tool_trace.tool_name,
            start_time=tool_trace.start_time,
            end_time=tool_trace.end_time,
            duration_ms=tool_trace.duration_ms,
            status=tool_trace.status.value,
        )
        for tool_trace in trace.tool_traces
    ]
    entries += [
        TimelineEntry(
            kind="ai_call",
            name=f"{ai_call.provider}:{ai_call.model}",
            start_time=ai_call.start_time,
            end_time=ai_call.end_time,
            duration_ms=ai_call.latency_ms,
            status="completed",
        )
        for ai_call in trace.ai_calls
    ]
    entries += [
        TimelineEntry(
            kind="approval",
            name=approval.metadata.get("node_name", approval.step_id),
            start_time=approval.requested_at,
            end_time=approval.approved_at,
            duration_ms=(
                (approval.approved_at - approval.requested_at).total_seconds() * 1000
                if approval.approved_at is not None
                else None
            ),
            status=approval.status.value,
        )
        for approval in trace.approval_traces
    ]
    return sorted(entries, key=lambda entry: entry.start_time)
