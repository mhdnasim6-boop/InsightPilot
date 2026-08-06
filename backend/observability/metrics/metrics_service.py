"""MetricsService: derived, aggregate statistics computed over every known trace.

Deliberately not part of ``ExecutionTrace``/``ObservabilityService`` —
a trace is a fact about *one* execution; a metric ("average SQL agent
latency") is a statistic over *many* traces. Embedding running
aggregates inside ``ExecutionTrace`` would mean every trace mutates
whenever a sibling trace is recorded, which would break the immutability
every trace is supposed to guarantee (see ``ExecutionTrace``'s own
docstring). Instead this class is a pure, stateless read-side
aggregator: every method recomputes its answer from
``ObservabilityService.list_traces()`` (in-progress snapshots and
finalized traces alike) on every call, so it can be thrown away and
rebuilt at any time with zero data loss — there is nothing to persist,
nothing that can drift out of sync with the traces it reads.
"""

from backend.observability.metrics.models import (
    AgentMetrics,
    AIMetrics,
    ExecutionMetricsSummary,
    ToolMetrics,
)
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.state.state import ExecutionStatus


class MetricsService:
    """Computes agent/tool/AI/approval aggregate metrics over every trace ObservabilityService knows about."""

    def __init__(self, observability_service: ObservabilityService) -> None:
        self._observability_service = observability_service

    def agent_metrics(self) -> list[AgentMetrics]:
        """Per-agent call count, failure count, and latency, across every trace."""
        by_agent: dict[str, AgentMetrics] = {}
        for trace in self._observability_service.list_traces():
            for agent_trace in trace.agent_traces:
                metrics = by_agent.setdefault(agent_trace.agent_name, AgentMetrics(agent_name=agent_trace.agent_name))
                metrics.call_count += 1
                metrics.total_duration_ms += agent_trace.duration_ms
                metrics.total_tool_calls += len(agent_trace.tool_calls)
                if agent_trace.status == ExecutionStatus.FAILED:
                    metrics.failed_count += 1
                elif agent_trace.status == ExecutionStatus.COMPLETED:
                    metrics.completed_count += 1
        for metrics in by_agent.values():
            metrics.average_duration_ms = metrics.total_duration_ms / metrics.call_count if metrics.call_count else 0.0
        return sorted(by_agent.values(), key=lambda m: m.agent_name)

    def tool_metrics(self) -> list[ToolMetrics]:
        """Per-tool call count, failure count, and latency, across every trace."""
        by_tool: dict[str, ToolMetrics] = {}
        for trace in self._observability_service.list_traces():
            for tool_trace in trace.tool_traces:
                metrics = by_tool.setdefault(tool_trace.tool_name, ToolMetrics(tool_name=tool_trace.tool_name))
                metrics.call_count += 1
                metrics.total_duration_ms += tool_trace.duration_ms
                if tool_trace.status == ExecutionStatus.FAILED:
                    metrics.failed_count += 1
                elif tool_trace.status == ExecutionStatus.COMPLETED:
                    metrics.completed_count += 1
        for metrics in by_tool.values():
            metrics.average_duration_ms = metrics.total_duration_ms / metrics.call_count if metrics.call_count else 0.0
        return sorted(by_tool.values(), key=lambda m: m.tool_name)

    def ai_metrics(self) -> AIMetrics:
        """Aggregate AI provider call count, token usage, cost, and latency, across every trace."""
        metrics = AIMetrics()
        total_latency = 0.0
        for trace in self._observability_service.list_traces():
            for ai_call in trace.ai_calls:
                metrics.call_count += 1
                metrics.total_prompt_tokens += ai_call.tokens.prompt_tokens
                metrics.total_completion_tokens += ai_call.tokens.completion_tokens
                metrics.total_tokens += ai_call.tokens.total_tokens
                metrics.total_estimated_cost += ai_call.estimated_cost
                total_latency += ai_call.latency_ms
        metrics.average_latency_ms = total_latency / metrics.call_count if metrics.call_count else 0.0
        return metrics

    def summary(self) -> ExecutionMetricsSummary:
        """Plan/approval-level aggregate statistics, plus the agent/tool/AI breakdowns above."""
        traces = self._observability_service.list_traces()
        completed_durations = [t.duration_ms for t in traces if t.duration_ms is not None]
        approval_latencies_ms = [
            (a.approved_at - a.requested_at).total_seconds() * 1000
            for t in traces
            for a in t.approval_traces
            if a.approved_at is not None
        ]
        approval_count = sum(len(t.approval_traces) for t in traces)
        tool_call_count = sum(len(t.tool_traces) for t in traces)
        ai_call_count = sum(len(t.ai_calls) for t in traces)

        return ExecutionMetricsSummary(
            trace_count=len(traces),
            total_execution_time_ms=sum(completed_durations),
            average_execution_time_ms=(
                sum(completed_durations) / len(completed_durations) if completed_durations else 0.0
            ),
            number_of_tool_calls=tool_call_count,
            number_of_ai_calls=ai_call_count,
            number_of_approvals=approval_count,
            average_approval_latency_ms=(
                sum(approval_latencies_ms) / len(approval_latencies_ms) if approval_latencies_ms else 0.0
            ),
            agent_metrics=self.agent_metrics(),
            tool_metrics=self.tool_metrics(),
            ai_metrics=self.ai_metrics(),
        )
