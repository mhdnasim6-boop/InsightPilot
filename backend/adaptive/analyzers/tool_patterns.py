"""tool_patterns: detects frequently reused datasets/reports/visualizations
and frequently used tools.

Reuses ``MemoryService.search()`` directly (Phase 29's own deterministic
retrieval) for dataset/report/visualization counts, and Phase 31's own
``tool_summary["calls_per_tool"]`` (already embedded in every
``ReflectionResult``) for tool usage — never a second lookup mechanism.
"""

from typing import Any

from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.reflection.models.reflection_result import ReflectionResult


def analyze_tool_patterns(memory_service: MemoryService, reflections: list[ReflectionResult]) -> dict[str, Any]:
    """Summarize reused artifacts (datasets/reports/visualizations) and overall tool usage."""
    dataset_count = memory_service.search(MemoryQuery(memory_type=MemoryType.DATASET)).total_matched
    report_count = memory_service.search(MemoryQuery(memory_type=MemoryType.REPORT)).total_matched
    visualization_count = memory_service.search(MemoryQuery(memory_type=MemoryType.VISUALIZATION)).total_matched

    tool_usage_counts: dict[str, int] = {}
    for reflection in reflections:
        for tool_name, count in reflection.review.tool_summary.get("calls_per_tool", {}).items():
            tool_usage_counts[tool_name] = tool_usage_counts.get(tool_name, 0) + count

    return {
        "reused_dataset_count": dataset_count,
        "reused_report_count": report_count,
        "reused_visualization_count": visualization_count,
        "tool_usage_counts": tool_usage_counts,
    }
