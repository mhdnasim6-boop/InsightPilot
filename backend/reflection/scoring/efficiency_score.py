"""EfficiencyScore: a deterministic 0-100 score for how well time was used.

"Parallel efficiency" needs no new instrumentation: ``trace.agent_traces``
already carries each agent's own ``duration_ms``, so comparing their sum
(the hypothetical fully-sequential time) against the trace's own actual
wall-clock ``duration_ms`` directly measures how much concurrency was
achieved — the same relationship
``test_execution_dag_scheduler.py::test_independent_steps_execute_concurrently_not_sequentially``
proves with a stopwatch, computed here from data that already exists.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.observability.models.execution_trace import ExecutionTrace
from backend.reflection.scoring.execution_score import label_for


class EfficiencyScore(BaseModel):
    """How efficiently the execution used time: parallelism achieved, approval wait."""

    model_config = ConfigDict(frozen=True)

    value: float = Field(ge=0.0, le=100.0)
    breakdown: dict[str, float] = Field(default_factory=dict)
    label: str


def compute_efficiency_score(trace: ExecutionTrace, approval_summary: dict[str, Any]) -> EfficiencyScore:
    """Score time efficiency from parallel gain (agent durations vs. wall time) and approval wait.

    ``approval_summary`` is ``approval_analyzer.analyze_approvals(trace)``'s
    own output — reused, never recomputed here.
    """
    breakdown: dict[str, float] = {}

    if len(trace.agent_traces) > 1 and trace.duration_ms and trace.duration_ms > 0:
        serial_sum_ms = sum(agent.duration_ms for agent in trace.agent_traces)
        parallel_ratio = serial_sum_ms / trace.duration_ms
        parallel_score = min(100.0, 50.0 * parallel_ratio)
    else:
        parallel_score = 100.0
    breakdown["parallel_efficiency"] = parallel_score

    approval_delay_penalty = 0.0
    if approval_summary["total_approvals"] > 0:
        approval_delay_penalty = min(30.0, approval_summary["average_delay_seconds"] / 10.0)
    breakdown["approval_delay_penalty"] = -approval_delay_penalty

    value = max(0.0, min(100.0, parallel_score - approval_delay_penalty))
    return EfficiencyScore(value=value, breakdown=breakdown, label=label_for(value))
