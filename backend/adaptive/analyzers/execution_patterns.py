"""execution_patterns: detects recurring execution bottlenecks across many
ReflectionResults.

Reuses Phase 31's own ``EfficiencyScore``/``tool_summary`` fields —
already computed from real ``ExecutionTrace`` data — never a second
timing mechanism.
"""

from statistics import mean
from typing import Any

from backend.reflection.models.reflection_result import ReflectionResult

_LOW_EFFICIENCY_THRESHOLD = 65.0
_BOTTLENECK_REPEAT_THRESHOLD = 2


def analyze_execution_patterns(reflections: list[ReflectionResult]) -> dict[str, Any]:
    """Summarize efficiency trends and repeated bottlenecks across ``reflections``."""
    if not reflections:
        return {
            "sample_size": 0,
            "average_efficiency_score": 0.0,
            "low_efficiency_count": 0,
            "average_tool_duration_ms": 0.0,
            "bottleneck_detected": False,
        }

    efficiencies = [r.review.efficiency_score.value for r in reflections]
    low_efficiency_count = sum(1 for value in efficiencies if value < _LOW_EFFICIENCY_THRESHOLD)
    tool_durations = [r.review.tool_summary.get("average_duration_ms", 0.0) for r in reflections]

    return {
        "sample_size": len(reflections),
        "average_efficiency_score": mean(efficiencies),
        "low_efficiency_count": low_efficiency_count,
        "average_tool_duration_ms": mean(tool_durations) if tool_durations else 0.0,
        "bottleneck_detected": low_efficiency_count >= _BOTTLENECK_REPEAT_THRESHOLD,
    }
