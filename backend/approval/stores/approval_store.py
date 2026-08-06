"""In-memory approval_id -> ExecutionApproval store, plus plan/status-scoped lookups.

Mirrors every other *Store in this codebase (BusinessDatasetStore,
AgentExecutionResultStore, ...) — a plain dict, process-wide singleton
via DI, no persistence backend yet.
"""

from backend.approval.models.approval import ApprovalStatus, ExecutionApproval


class ApprovalStore:
    """Process-wide store of ExecutionApprovals, keyed by approval_id."""

    def __init__(self) -> None:
        self._approvals: dict[str, ExecutionApproval] = {}

    def put(self, approval: ExecutionApproval) -> None:
        """Store (or overwrite) an approval, keyed by its own ``approval_id``."""
        self._approvals[approval.approval_id] = approval

    def get(self, approval_id: str) -> ExecutionApproval | None:
        """Return the approval for an approval_id, or None if not present."""
        return self._approvals.get(approval_id)

    def list_all(self) -> list[ExecutionApproval]:
        """Return every stored approval, most recently added first."""
        return list(reversed(self._approvals.values()))

    def list_pending(self) -> list[ExecutionApproval]:
        """Return every PENDING approval, most recently added first."""
        return [approval for approval in self.list_all() if approval.status == ApprovalStatus.PENDING]

    def list_for_plan(self, plan_id: str) -> list[ExecutionApproval]:
        """Return every approval requested for a given plan, most recently added first."""
        return [approval for approval in self.list_all() if approval.plan_id == plan_id]
