"""ApprovalPublisher: ApprovalRequested/Granted/Rejected.

Wraps ``ApprovalService`` — every other method (``get``, ``list_pending``,
``list_for_plan``, ``history_for_plan``, ``record_resumed``, ``record_cancelled``,
``record_completed``) is forwarded unchanged via ``__getattr__``. Wired
into ``get_approval_service()`` (``backend.dependencies.approval``),
wrapping at the single source every consumer (``DAGScheduler``,
``WorkflowService``, the ``/approvals`` router) already depends on —
including ``ApprovalRequested``, which is only ever raised *internally*
by ``DAGScheduler.run()``, never through a REST call, so wrapping at any
router alone could never have observed it.
"""

from typing import Any

from backend.approval.models.approval import ExecutionApproval
from backend.approval.services.approval_service import ApprovalService
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService


class RealtimePublishingApprovalService:
    """Wraps a real ApprovalService, publishing Approval* events around request/approve/reject."""

    def __init__(self, inner: ApprovalService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    def request_approval(
        self, plan_id: str, step_id: str, node_name: str, execution_id: str, reason: str | None = None
    ) -> ExecutionApproval:
        approval = self._inner.request_approval(plan_id, step_id, node_name, execution_id, reason)
        self._publish(EventType.APPROVAL_REQUESTED, approval, execution_id=execution_id)
        return approval

    def approve(self, approval_id: str, approver: str | None = None) -> ExecutionApproval:
        approval = self._inner.approve(approval_id, approver)
        self._publish(EventType.APPROVAL_GRANTED, approval)
        return approval

    def reject(self, approval_id: str, approver: str | None = None, reason: str | None = None) -> ExecutionApproval:
        approval = self._inner.reject(approval_id, approver, reason)
        self._publish(EventType.APPROVAL_REJECTED, approval)
        return approval

    def _publish(self, event_type: EventType, approval: ExecutionApproval, execution_id: str | None = None) -> None:
        node_name = approval.metadata.get("node_name")
        self._realtime_service.publish(
            Event(
                event_type=event_type,
                plan_id=approval.plan_id,
                step_id=approval.step_id,
                execution_id=execution_id or approval.metadata.get("execution_id"),
                agent_name=node_name,
                data={"approval_id": approval.approval_id, "status": approval.status.value, "reason": approval.reason},
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
