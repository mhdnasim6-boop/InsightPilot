"""MemoryAnalyzer: was there relevant prior knowledge for this request?

Reuses ``MemoryService.search()`` directly — the exact deterministic,
keyword-based retrieval Phase 29 already built — never a new lookup
mechanism. Excludes memories produced *by this same plan* (its own
DECISION/EXECUTION memories, already written by the time reflection
runs) so "reused memory" only ever counts genuine prior knowledge.
"""

from typing import Any

from backend.memory.models.memory_query import MemoryQuery
from backend.memory.services.memory_service import MemoryService
from backend.planning.models.plan import ExecutionPlan


def analyze_memory(memory_service: MemoryService | None, plan: ExecutionPlan) -> dict[str, Any]:
    """Summarize whatever relevant prior memory existed for ``plan``'s own goal."""
    if memory_service is None or not plan.goal:
        return {"relevant_prior_count": 0, "relevant_titles": [], "reused_memory": False}

    result = memory_service.search(MemoryQuery(keyword=plan.goal, top_k=5))
    relevant = [item for item in result.items if item.content.get("plan_id") != plan.plan_id]

    return {
        "relevant_prior_count": len(relevant),
        "relevant_titles": [item.title for item in relevant],
        "reused_memory": len(relevant) > 0,
    }
