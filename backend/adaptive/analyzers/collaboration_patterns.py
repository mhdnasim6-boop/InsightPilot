"""collaboration_patterns: detects repeated collaboration outcomes.

Reads the ``MemoryType.COLLABORATION`` memories ``CollaborationService``
already writes on every terminal session (Phase 30's
``_remember_session()``) — never a live ``CollaborationService.list_sessions()``
call. This is deliberate, not just a convenience: depending on the full
``CollaborationService`` here would pull in its own execution-engine
dependency chain (down to ``get_capability_registry()`` -> ``get_graph_builder()``
-> ``get_planner_service()``), and ``AdaptivePlanningService`` is itself a
dependency of ``get_planner_service()`` (see Planner Integration) — a
real circular DI dependency, the exact class of problem Phase 30 already
solved once by excluding "planner" from its own dispatcher. Reading the
already-persisted Memory record instead breaks the cycle the same way.
"""

from typing import Any

from backend.memory.models.memory_item import MemoryItem


def analyze_collaboration_patterns(collaboration_memories: list[MemoryItem]) -> dict[str, Any]:
    """Summarize how collaboration sessions have historically gone.

    ``content["failed_subtasks"]``/``["completed_subtasks"]`` are lists
    of subtask ids (``CollaborationService._remember_session()``'s own
    shape), not counts — always measured by length here, never compared
    directly.
    """
    total = len(collaboration_memories)
    completed = sum(1 for item in collaboration_memories if item.content.get("status") == "completed")
    with_failures = sum(1 for item in collaboration_memories if len(item.content.get("failed_subtasks") or []) > 0)

    return {
        "total_collaborations": total,
        "completed_collaboration_count": completed,
        "collaboration_with_failures_count": with_failures,
    }
