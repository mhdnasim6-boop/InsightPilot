"""Metrics response models: aggregate statistics derived from ExecutionTraces.

Deliberately separate from the trace models — these are computed fresh
on every request from whatever traces currently exist, never stored or
mutated themselves. See ``MetricsService`` for why aggregation lives
here rather than on ``ExecutionTrace`` itself.
"""

from pydantic import BaseModel, Field


class AgentMetrics(BaseModel):
    """Aggregate statistics for one agent (orchestration node), across every trace."""

    agent_name: str
    call_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    total_duration_ms: float = 0.0
    average_duration_ms: float = 0.0
    total_tool_calls: int = 0


class ToolMetrics(BaseModel):
    """Aggregate statistics for one tool, across every trace."""

    tool_name: str
    call_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    total_duration_ms: float = 0.0
    average_duration_ms: float = 0.0


class AIMetrics(BaseModel):
    """Aggregate statistics for AI provider calls, across every trace."""

    call_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_estimated_cost: float = 0.0
    average_latency_ms: float = 0.0


class ExecutionMetricsSummary(BaseModel):
    """Plan/approval-level aggregate statistics, across every trace."""

    trace_count: int = 0
    total_execution_time_ms: float = 0.0
    average_execution_time_ms: float = 0.0
    number_of_tool_calls: int = 0
    number_of_ai_calls: int = 0
    number_of_approvals: int = 0
    average_approval_latency_ms: float = 0.0
    agent_metrics: list[AgentMetrics] = Field(default_factory=list)
    tool_metrics: list[ToolMetrics] = Field(default_factory=list)
    ai_metrics: AIMetrics = Field(default_factory=AIMetrics)
