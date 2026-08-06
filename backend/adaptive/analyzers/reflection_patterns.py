"""reflection_patterns: detects repeated signals across many ReflectionResults.

Reuses Phase 31's own ``RecommendationCategory`` values as the pattern
signal — a single reflection's "FileAgent failed" advice becomes a
multi-execution *pattern* once it recurs. No new failure-detection logic
is written here; this module only counts what
``backend.reflection.analyzers.recommendation_engine`` already decided.
"""

from typing import Any

from backend.reflection.models.recommendation import RecommendationCategory
from backend.reflection.models.reflection_result import ReflectionResult


def analyze_reflection_patterns(reflections: list[ReflectionResult]) -> dict[str, Any]:
    """Count repeated FileAgent failures, SQL successes, approval delays, and BrowserAgent skips."""
    file_agent_failure_count = sum(
        1
        for r in reflections
        if any(
            rec.category == RecommendationCategory.TOOL_CHOICE and "FileAgent" in rec.reason
            for rec in r.review.recommendations
        )
    )
    sql_success_count = sum(
        1
        for r in reflections
        if r.review.overall_success and "query_database" in r.review.tool_summary.get("unique_tools", [])
    )
    approval_delay_count = sum(
        1
        for r in reflections
        if any(rec.category == RecommendationCategory.APPROVAL_POLICY for rec in r.review.recommendations)
    )
    browser_skip_count = sum(
        1
        for r in reflections
        if any(
            rec.category == RecommendationCategory.OTHER and "BrowserAgent" in rec.message
            for rec in r.review.recommendations
        )
    )

    return {
        "sample_size": len(reflections),
        "file_agent_failure_count": file_agent_failure_count,
        "sql_success_count": sql_success_count,
        "approval_delay_count": approval_delay_count,
        "browser_skip_count": browser_skip_count,
    }
