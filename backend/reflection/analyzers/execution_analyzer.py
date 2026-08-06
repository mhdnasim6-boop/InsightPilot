"""ExecutionAnalyzer: what happened, what succeeded, what failed, what was slow.

Reads only ``ExecutionTrace`` — every field it inspects
(``agent_traces``, ``errors``, ``warnings``, ``status``, ``duration_ms``)
already exists on the trace ``ObservabilityService`` produces; this
module adds no new instrumentation, only interpretation.
"""

from typing import Any

from backend.observability.models.execution_trace import ExecutionTrace
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore

_SLOW_AGENT_THRESHOLD_MS = 5000.0


def analyze_execution(trace: ExecutionTrace) -> dict[str, Any]:
    """Summarize what happened in ``trace``: success, failures, slow agents, errors/warnings."""
    completed_agents = [a.agent_name for a in trace.agent_traces if a.status == ExecutionStatus.COMPLETED]
    failed_agents = [a.agent_name for a in trace.agent_traces if a.status == ExecutionStatus.FAILED]
    slow_agents = [a.agent_name for a in trace.agent_traces if a.duration_ms >= _SLOW_AGENT_THRESHOLD_MS]

    return {
        "overall_success": trace.status == PlanStatus.COMPLETED and not failed_agents,
        "duration_ms": trace.duration_ms,
        "agent_count": len(trace.agent_traces),
        "completed_agents": completed_agents,
        "failed_agents": failed_agents,
        "slow_agents": slow_agents,
        "error_count": len(trace.errors),
        "warning_count": len(trace.warnings),
    }


def derive_strengths_and_weaknesses(
    execution_summary: dict[str, Any],
    tool_summary: dict[str, Any],
    approval_summary: dict[str, Any],
    efficiency_score: EfficiencyScore,
    confidence_score: ConfidenceScore,
) -> tuple[list[str], list[str]]:
    """Turn the other analyzers' output into plain-language strengths/weaknesses."""
    strengths: list[str] = []
    weaknesses: list[str] = []

    if execution_summary["overall_success"]:
        strengths.append(f"Execution completed successfully across {execution_summary['agent_count']} agent(s).")
    else:
        weaknesses.append("Execution did not reach a successful, completed status.")

    if execution_summary["failed_agents"]:
        weaknesses.append(f"Agent(s) failed: {', '.join(execution_summary['failed_agents'])}.")

    if execution_summary["slow_agents"]:
        weaknesses.append(f"Slow agent(s) (>{_SLOW_AGENT_THRESHOLD_MS / 1000:.0f}s): {', '.join(execution_summary['slow_agents'])}.")

    if tool_summary["failed_tools"]:
        weaknesses.append(f"Tool call(s) failed: {', '.join(tool_summary['failed_tools'])}.")
    elif tool_summary["total_calls"] > 0:
        strengths.append(f"All {tool_summary['total_calls']} tool call(s) succeeded.")

    if approval_summary["rejected_count"] > 0:
        weaknesses.append(f"{approval_summary['rejected_count']} approval(s) were rejected.")
    elif approval_summary["total_approvals"] > 0:
        strengths.append(f"All {approval_summary['total_approvals']} approval gate(s) were granted.")

    if execution_summary["agent_count"] > 1 and efficiency_score.value >= 85.0:
        strengths.append("Independent agents ran with strong parallel efficiency.")
    elif efficiency_score.value < 50.0 and execution_summary["agent_count"] > 1:
        weaknesses.append("Independent agents ran with little to no parallel gain.")

    if confidence_score.value < 50.0:
        weaknesses.append("Low confidence in this outcome — review warnings/errors before reusing it.")

    return strengths, weaknesses
