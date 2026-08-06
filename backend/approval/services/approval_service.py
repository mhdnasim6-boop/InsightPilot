"""ApprovalService: the only entry point for creating, deciding, and inspecting approvals.

Also the one place ``ExecutionHistoryEvent``s get appended — every
approval-lifecycle transition (waiting/approved/rejected) and every
execution-lifecycle transition PlanExecutor reports (resumed/cancelled/
completed) flows through here, so a plan's full HITL timeline is always
assembled from one store, never scattered.

``memory_service`` is an optional collaborator: every decided approval
(approve/reject) is remembered as an APPROVAL memory — approver,
decision, timestamp, and reason/comment — the durable record this
phase's own "Approval Integration" asks for, on top of (never replacing)
``ExecutionHistoryEvent``'s own existing timeline.
"""

from backend.approval.exceptions import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
)
from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.approval.models.history import (
    ExecutionHistoryEvent,
    ExecutionHistoryEventType,
)
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class ApprovalService:
    """Runs the full lifecycle of an ExecutionApproval and records history for it."""

    def __init__(
        self,
        store: ApprovalStore,
        history_store: ExecutionHistoryStore,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._store = store
        self._history_store = history_store
        self._memory_service = memory_service

    def request_approval(
        self, plan_id: str, step_id: str, node_name: str, execution_id: str, reason: str | None = None
    ) -> ExecutionApproval:
        """Create a new PENDING approval for ``node_name``, gated on ``execution_id``'s paused run."""
        now = utc_now()
        approval = ExecutionApproval(
            approval_id=generate_id(),
            plan_id=plan_id,
            step_id=step_id,
            status=ApprovalStatus.PENDING,
            reason=reason,
            requested_at=now,
            metadata={"node_name": node_name, "execution_id": execution_id},
        )
        self._store.put(approval)
        self._append_history(
            plan_id=plan_id,
            step_id=step_id,
            approval_id=approval.approval_id,
            event_type=ExecutionHistoryEventType.WAITING,
            detail=reason,
        )
        return approval

    def approve(self, approval_id: str, approver: str | None = None) -> ExecutionApproval:
        """Approve a PENDING approval. Raises ApprovalAlreadyDecidedError if it isn't PENDING."""
        approval = self.get(approval_id)
        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalAlreadyDecidedError(
                f"Approval '{approval_id}' is already {approval.status.value}, not pending."
            )
        updated = approval.model_copy(
            update={"status": ApprovalStatus.APPROVED, "approved_at": utc_now(), "approver": approver}
        )
        self._store.put(updated)
        self._append_history(
            plan_id=updated.plan_id,
            step_id=updated.step_id,
            approval_id=updated.approval_id,
            event_type=ExecutionHistoryEventType.APPROVED,
            actor=approver,
        )
        self._remember_decision(updated)
        return updated

    def reject(self, approval_id: str, approver: str | None = None, reason: str | None = None) -> ExecutionApproval:
        """Reject a PENDING approval. Raises ApprovalAlreadyDecidedError if it isn't PENDING."""
        approval = self.get(approval_id)
        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalAlreadyDecidedError(
                f"Approval '{approval_id}' is already {approval.status.value}, not pending."
            )
        updated = approval.model_copy(
            update={
                "status": ApprovalStatus.REJECTED,
                "approved_at": utc_now(),
                "approver": approver,
                "reason": reason or approval.reason,
            }
        )
        self._store.put(updated)
        self._append_history(
            plan_id=updated.plan_id,
            step_id=updated.step_id,
            approval_id=updated.approval_id,
            event_type=ExecutionHistoryEventType.REJECTED,
            actor=approver,
            detail=reason,
        )
        self._remember_decision(updated)
        return updated

    def get(self, approval_id: str) -> ExecutionApproval:
        """Fetch an approval. Raises ApprovalNotFoundError if unknown."""
        approval = self._store.get(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"No approval found for '{approval_id}'.")
        return approval

    def list_pending(self) -> list[ExecutionApproval]:
        """Every PENDING approval, most recently requested first."""
        return self._store.list_pending()

    def list_for_plan(self, plan_id: str) -> list[ExecutionApproval]:
        """Every approval ever requested for a plan, most recently requested first."""
        return self._store.list_for_plan(plan_id)

    def history_for_plan(self, plan_id: str) -> list[ExecutionHistoryEvent]:
        """A plan's full HITL timeline, oldest first."""
        return self._history_store.list_for_plan(plan_id)

    def record_resumed(self, plan_id: str, step_id: str | None = None, detail: str | None = None) -> None:
        """Record that a plan's paused execution was resumed (with or without a prior approval)."""
        self._append_history(
            plan_id=plan_id, step_id=step_id, event_type=ExecutionHistoryEventType.RESUMED, detail=detail
        )

    def record_cancelled(self, plan_id: str, step_id: str | None = None, detail: str | None = None) -> None:
        """Record that a plan's paused execution was cancelled outright."""
        self._append_history(
            plan_id=plan_id, step_id=step_id, event_type=ExecutionHistoryEventType.CANCELLED, detail=detail
        )

    def record_completed(self, plan_id: str, detail: str | None = None) -> None:
        """Record that a plan finished executing (with or without ever pausing)."""
        self._append_history(plan_id=plan_id, event_type=ExecutionHistoryEventType.COMPLETED, detail=detail)

    def _remember_decision(self, approval: ExecutionApproval) -> None:
        if self._memory_service is None:
            return
        node_name = approval.metadata.get("node_name", "unknown agent")
        self._memory_service.remember(
            title=f"Approval {approval.status.value}: {node_name}",
            summary=approval.reason or f"{approval.status.value} by {approval.approver or 'unknown'}.",
            memory_type=MemoryType.APPROVAL,
            scope=MemoryScope.PROJECT,
            content={
                "approver": approval.approver,
                "decision": approval.status.value,
                "requested_at": approval.requested_at.isoformat(),
                "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
                "reason": approval.reason,
            },
            tags=["approval", node_name],
            references=[MemoryReference(reference_type="plan", reference_id=approval.plan_id)],
        )

    def _append_history(
        self,
        plan_id: str,
        event_type: ExecutionHistoryEventType,
        step_id: str | None = None,
        approval_id: str | None = None,
        actor: str | None = None,
        detail: str | None = None,
    ) -> None:
        self._history_store.append(
            ExecutionHistoryEvent(
                event_id=generate_id(),
                plan_id=plan_id,
                step_id=step_id,
                approval_id=approval_id,
                event_type=event_type,
                timestamp=utc_now(),
                actor=actor,
                detail=detail,
            )
        )
