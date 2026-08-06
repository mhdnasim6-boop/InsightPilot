"""Tests for backend.adaptive.analyzers: reflection, execution, collaboration,
and tool pattern detection — each a pure function over already-existing
models (ReflectionResult, MemoryItem), no AI, no network.
"""

from backend.adaptive.analyzers.collaboration_patterns import (
    analyze_collaboration_patterns,
)
from backend.adaptive.analyzers.execution_patterns import analyze_execution_patterns
from backend.adaptive.analyzers.reflection_patterns import analyze_reflection_patterns
from backend.adaptive.analyzers.tool_patterns import analyze_tool_patterns
from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_result import MemoryResult
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.reflection.models.execution_review import ExecutionReview
from backend.reflection.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
)
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore
from backend.reflection.scoring.execution_score import ExecutionScore
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


def _recommendation(category: RecommendationCategory, message: str = "", reason: str = "") -> Recommendation:
    return Recommendation(
        recommendation_id=generate_id(), category=category, message=message, reason=reason,
        priority=RecommendationPriority.MEDIUM,
    )


def _reflection(
    recommendations: list[Recommendation] | None = None,
    overall_success: bool = True,
    efficiency: float = 90.0,
    unique_tools: list[str] | None = None,
    calls_per_tool: dict[str, int] | None = None,
    average_duration_ms: float = 100.0,
) -> ReflectionResult:
    review = ExecutionReview(
        overall_success=overall_success,
        execution_score=ExecutionScore(value=80.0, breakdown={}, label="good"),
        efficiency_score=EfficiencyScore(value=efficiency, breakdown={}, label="good"),
        confidence_score=ConfidenceScore(value=80.0, breakdown={}, label="good"),
        recommendations=recommendations or [],
        tool_summary={
            "unique_tools": unique_tools or [],
            "calls_per_tool": calls_per_tool or {},
            "average_duration_ms": average_duration_ms,
            "failed_tools": [],
        },
    )
    return ReflectionResult(reflection_id="r1", plan_id="p1", trace_id="t1", review=review, generated_at=utc_now())


def _memory_item(memory_type: MemoryType, content: dict) -> MemoryItem:  # type: ignore[type-arg]
    now = utc_now()
    return MemoryItem(
        memory_id=generate_id(), title="x", summary="", memory_type=memory_type, scope=MemoryScope.PROJECT,
        created_at=now, updated_at=now, content=content,
    )


# -- reflection_patterns ---------------------------------------------------------------


def test_analyze_reflection_patterns_counts_file_agent_failures() -> None:
    reflections = [
        _reflection([_recommendation(RecommendationCategory.TOOL_CHOICE, reason="FileAgent failed during this execution.")]),
        _reflection([_recommendation(RecommendationCategory.TOOL_CHOICE, reason="FileAgent failed during this execution.")]),
        _reflection([]),
    ]
    patterns = analyze_reflection_patterns(reflections)
    assert patterns["file_agent_failure_count"] == 2
    assert patterns["sample_size"] == 3


def test_analyze_reflection_patterns_counts_sql_successes() -> None:
    reflections = [
        _reflection(overall_success=True, unique_tools=["query_database"]),
        _reflection(overall_success=False, unique_tools=["query_database"]),  # failed run doesn't count
        _reflection(overall_success=True, unique_tools=["ingest_dataset"]),  # not SQL
    ]
    patterns = analyze_reflection_patterns(reflections)
    assert patterns["sql_success_count"] == 1


def test_analyze_reflection_patterns_counts_approval_delays_and_browser_skips() -> None:
    reflections = [
        _reflection([_recommendation(RecommendationCategory.APPROVAL_POLICY)]),
        _reflection([_recommendation(RecommendationCategory.OTHER, message="Avoid delegating to BrowserAgent when there is no external research need.")]),
    ]
    patterns = analyze_reflection_patterns(reflections)
    assert patterns["approval_delay_count"] == 1
    assert patterns["browser_skip_count"] == 1


def test_analyze_reflection_patterns_with_no_reflections() -> None:
    patterns = analyze_reflection_patterns([])
    assert patterns["sample_size"] == 0
    assert patterns["file_agent_failure_count"] == 0


# -- execution_patterns ----------------------------------------------------------------


def test_analyze_execution_patterns_computes_average_efficiency() -> None:
    reflections = [_reflection(efficiency=90.0), _reflection(efficiency=50.0)]
    patterns = analyze_execution_patterns(reflections)
    assert patterns["average_efficiency_score"] == 70.0
    assert patterns["low_efficiency_count"] == 1
    assert patterns["bottleneck_detected"] is False  # only one low-efficiency reflection


def test_analyze_execution_patterns_detects_repeated_bottleneck() -> None:
    reflections = [_reflection(efficiency=40.0), _reflection(efficiency=45.0)]
    patterns = analyze_execution_patterns(reflections)
    assert patterns["bottleneck_detected"] is True


def test_analyze_execution_patterns_with_no_reflections() -> None:
    patterns = analyze_execution_patterns([])
    assert patterns["sample_size"] == 0
    assert patterns["bottleneck_detected"] is False


# -- collaboration_patterns -------------------------------------------------------------


def test_analyze_collaboration_patterns_counts_failures_by_list_length() -> None:
    """content['failed_subtasks'] is a list of subtask ids, not a count — this is the
    real bug this phase's own testing caught (see collaboration_patterns.py docstring).
    """
    memories = [
        _memory_item(MemoryType.COLLABORATION, {"status": "completed", "failed_subtasks": []}),
        _memory_item(MemoryType.COLLABORATION, {"status": "cancelled", "failed_subtasks": ["st1", "st2"]}),
    ]
    patterns = analyze_collaboration_patterns(memories)
    assert patterns["total_collaborations"] == 2
    assert patterns["completed_collaboration_count"] == 1
    assert patterns["collaboration_with_failures_count"] == 1


def test_analyze_collaboration_patterns_with_no_memories() -> None:
    patterns = analyze_collaboration_patterns([])
    assert patterns["total_collaborations"] == 0


# -- tool_patterns -----------------------------------------------------------------------


class _StubMemoryService:
    def __init__(self, counts: dict[MemoryType, int]) -> None:
        self._counts = counts

    def search(self, query: MemoryQuery) -> MemoryResult:
        count = self._counts.get(query.memory_type, 0)  # type: ignore[arg-type]
        return MemoryResult(items=[], total_matched=count, query=query)


def test_analyze_tool_patterns_counts_reused_artifacts_and_tool_usage() -> None:
    memory_service = _StubMemoryService(
        {MemoryType.DATASET: 3, MemoryType.REPORT: 1, MemoryType.VISUALIZATION: 2}
    )
    reflections = [
        _reflection(calls_per_tool={"ingest_dataset": 1, "clean_dataset": 1}),
        _reflection(calls_per_tool={"ingest_dataset": 2}),
    ]
    patterns = analyze_tool_patterns(memory_service, reflections)  # type: ignore[arg-type]
    assert patterns["reused_dataset_count"] == 3
    assert patterns["reused_report_count"] == 1
    assert patterns["reused_visualization_count"] == 2
    assert patterns["tool_usage_counts"] == {"ingest_dataset": 3, "clean_dataset": 1}
