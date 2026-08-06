"""Tests for backend.reflection.analyzers.recommendation_engine: every rule
reacts to one concrete fact from the other analyzers' own output.
"""

from backend.reflection.analyzers.recommendation_engine import generate_recommendations
from backend.reflection.models.recommendation import RecommendationCategory


def _summaries(**overrides: dict) -> tuple[dict, dict, dict, dict, dict]:
    execution_summary = {
        "overall_success": True,
        "agent_count": 1,
        "completed_agents": [],
        "failed_agents": [],
        "slow_agents": [],
    }
    tool_summary = {"failed_tools": [], "total_calls": 0, "calls_per_tool": {}}
    approval_summary = {"total_approvals": 0, "rejected_count": 0, "average_delay_seconds": 0.0}
    memory_summary = {"reused_memory": False, "relevant_prior_count": 0}
    collaboration_summary = {"used_collaboration": False, "failed_subtasks": 0, "subtask_count": 0}
    merged = {
        "execution_summary": execution_summary,
        "tool_summary": tool_summary,
        "approval_summary": approval_summary,
        "memory_summary": memory_summary,
        "collaboration_summary": collaboration_summary,
    }
    for key, value in overrides.items():
        merged[key].update(value)  # type: ignore[attr-defined]
    return (
        merged["execution_summary"],
        merged["tool_summary"],
        merged["approval_summary"],
        merged["memory_summary"],
        merged["collaboration_summary"],
    )


def test_no_recommendations_for_a_clean_run_with_no_prior_memory() -> None:
    execution, tool, approval, memory, collaboration = _summaries()
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    assert len(recommendations) == 1
    assert recommendations[0].category == RecommendationCategory.MEMORY_REUSE


def test_failed_tool_produces_a_retry_recommendation() -> None:
    execution, tool, approval, memory, collaboration = _summaries(tool_summary={"failed_tools": ["query_database"]})
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    retry = [r for r in recommendations if r.category == RecommendationCategory.RETRY]
    assert len(retry) == 1
    assert "query_database" in retry[0].message


def test_failed_file_agent_suggests_sql_agent() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        execution_summary={"failed_agents": ["file_agent"]}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    tool_choice = [r for r in recommendations if r.category == RecommendationCategory.TOOL_CHOICE]
    assert len(tool_choice) == 1
    assert "SQLAgent" in tool_choice[0].message


def test_approval_rejection_suggests_relaxing_policy() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        approval_summary={"total_approvals": 1, "rejected_count": 1}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    assert any(r.category == RecommendationCategory.APPROVAL_POLICY for r in recommendations)


def test_high_approval_delay_suggests_relaxing_policy() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        approval_summary={"total_approvals": 1, "average_delay_seconds": 90.0}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    assert any(r.category == RecommendationCategory.APPROVAL_POLICY for r in recommendations)


def test_low_approval_delay_does_not_trigger_recommendation() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        approval_summary={"total_approvals": 1, "average_delay_seconds": 5.0}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    assert not any(r.category == RecommendationCategory.APPROVAL_POLICY for r in recommendations)


def test_slow_multi_agent_run_suggests_parallelization() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        execution_summary={"agent_count": 2, "slow_agents": ["browser_agent"]}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    assert any(r.category == RecommendationCategory.PARALLELIZATION for r in recommendations)


def test_reused_memory_suggests_caching_instead_of_recompute() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        memory_summary={"reused_memory": True, "relevant_prior_count": 2}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    caching = [r for r in recommendations if r.category == RecommendationCategory.CACHING]
    assert len(caching) == 1
    assert "2" in caching[0].reason


def test_unused_browser_agent_suggests_avoiding_it() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        execution_summary={"completed_agents": ["browser_agent"]}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    other = [r for r in recommendations if r.category == RecommendationCategory.OTHER]
    assert len(other) == 1
    assert "BrowserAgent" in other[0].message


def test_browser_agent_that_actually_searched_does_not_trigger_avoid_recommendation() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        execution_summary={"completed_agents": ["browser_agent"]},
        tool_summary={"calls_per_tool": {"search_web": 1}},
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    assert not any(r.category == RecommendationCategory.OTHER for r in recommendations)


def test_failed_collaboration_subtask_suggests_retry() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        collaboration_summary={"used_collaboration": True, "failed_subtasks": 1, "subtask_count": 3}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    retry = [r for r in recommendations if r.category == RecommendationCategory.RETRY]
    assert any("collaboration" in r.message.lower() for r in retry)


def test_every_recommendation_has_a_unique_id() -> None:
    execution, tool, approval, memory, collaboration = _summaries(
        tool_summary={"failed_tools": ["ingest_dataset", "query_database"]}
    )
    recommendations = generate_recommendations(execution, tool, approval, memory, collaboration)
    ids = [r.recommendation_id for r in recommendations]
    assert len(ids) == len(set(ids))
