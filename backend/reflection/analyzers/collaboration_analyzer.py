"""CollaborationAnalyzer: how much (if any) delegated, multi-agent work happened.

Reads only ``CollaborationTask`` (Phase 30) — ``subtask_ids_with_status()``
is that model's own existing helper, never reimplemented here.
"""

from typing import Any

from backend.collaboration.models.collaboration_task import CollaborationTask
from backend.execution.state.node_status import NodeStatus


def analyze_collaboration(collaboration_task: CollaborationTask | None) -> dict[str, Any]:
    """Summarize a collaboration session's subtask outcomes, if one was involved."""
    if collaboration_task is None:
        return {"used_collaboration": False, "subtask_count": 0, "completed_subtasks": 0, "failed_subtasks": 0, "status": None}

    completed = len(collaboration_task.subtask_ids_with_status(NodeStatus.COMPLETED))
    failed = len(collaboration_task.subtask_ids_with_status(NodeStatus.FAILED, NodeStatus.CANCELLED))

    return {
        "used_collaboration": True,
        "subtask_count": len(collaboration_task.subtasks),
        "completed_subtasks": completed,
        "failed_subtasks": failed,
        "status": collaboration_task.status.value,
    }
