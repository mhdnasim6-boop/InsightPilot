"""ApprovalAnalyzer: what approvals were required, and how long they took.

Reads only ``trace.approval_traces`` — reuses ``ExecutionApproval``
directly (``ObservabilityService.set_approvals()`` already populates it
straight from ``ApprovalService.list_for_plan()``); this module adds no
new approval tracking of its own.
"""

from typing import Any

from backend.approval.models.approval import ApprovalStatus
from backend.observability.models.execution_trace import ExecutionTrace


def analyze_approvals(trace: ExecutionTrace) -> dict[str, Any]:
    """Summarize every approval gate recorded in ``trace``."""
    approvals = trace.approval_traces
    approved = [a for a in approvals if a.status == ApprovalStatus.APPROVED]
    rejected = [a for a in approvals if a.status == ApprovalStatus.REJECTED]
    pending = [a for a in approvals if a.status == ApprovalStatus.PENDING]

    delays_seconds = [
        (a.approved_at - a.requested_at).total_seconds() for a in approved if a.approved_at is not None
    ]
    average_delay_seconds = (sum(delays_seconds) / len(delays_seconds)) if delays_seconds else 0.0
    max_delay_seconds = max(delays_seconds) if delays_seconds else 0.0

    return {
        "total_approvals": len(approvals),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "pending_count": len(pending),
        "average_delay_seconds": average_delay_seconds,
        "max_delay_seconds": max_delay_seconds,
    }
