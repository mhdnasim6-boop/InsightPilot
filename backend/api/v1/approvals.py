"""Approval endpoints: list pending approvals, approve, reject, resume execution,
cancel execution, and configure the active ApprovalPolicy.

Thin HTTP wrappers only — every endpoint here is a direct call into the
existing ``ApprovalService``/``ApprovalPolicyService``/``PlanningService``,
never a parallel implementation. Approving/rejecting an
``ExecutionApproval`` only records the *decision*; nothing runs until a
separate call to ``POST /approvals/plan/{plan_id}/resume``, mirroring
how ``POST /planner/execute`` is itself a separate step after a plan is
generated.
"""

from fastapi import APIRouter, Depends

from backend.approval.models.approval import ExecutionApproval
from backend.approval.models.history import ExecutionHistoryEvent
from backend.approval.policies.approval_policy import ApprovalPolicy
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.dependencies.approval import (
    get_approval_policy_service,
    get_approval_service,
)
from backend.dependencies.planning import get_planning_service
from backend.planning.models.plan import ExecutionPlan
from backend.schemas.approval_request import (
    ApprovalDecisionRequest,
    ApprovalPolicyRequest,
    ApprovalRejectionRequest,
)
from backend.schemas.response import SuccessResponse
from backend.services.planning_service import PlanningService

router = APIRouter(prefix="/approvals")


@router.get("/pending", response_model=SuccessResponse[list[ExecutionApproval]], summary="List pending approvals")
async def list_pending_approvals(
    service: ApprovalService = Depends(get_approval_service),
) -> SuccessResponse[list[ExecutionApproval]]:
    """Every approval currently awaiting a human decision, most recently requested first."""
    return SuccessResponse.ok(data=service.list_pending(), message="Pending approvals fetched.")


@router.get("/policy", response_model=SuccessResponse[ApprovalPolicy], summary="Get the active approval policy")
async def get_active_policy(
    service: ApprovalPolicyService = Depends(get_approval_policy_service),
) -> SuccessResponse[ApprovalPolicy]:
    """The currently active ApprovalPolicy — default NEVER (HITL is opt-in)."""
    return SuccessResponse.ok(data=service.get_policy(), message="Active policy fetched.")


@router.put("/policy", response_model=SuccessResponse[ApprovalPolicy], summary="Set the active approval policy")
async def set_active_policy(
    request: ApprovalPolicyRequest,
    service: ApprovalPolicyService = Depends(get_approval_policy_service),
) -> SuccessResponse[ApprovalPolicy]:
    """Replace the active ApprovalPolicy. Affects every plan executed from now on."""
    policy = service.set_policy(ApprovalPolicy(policy_type=request.policy_type))
    return SuccessResponse.ok(data=policy, message="Active policy updated.")


@router.get(
    "/{approval_id}", response_model=SuccessResponse[ExecutionApproval], summary="Get one approval"
)
async def get_approval(
    approval_id: str, service: ApprovalService = Depends(get_approval_service)
) -> SuccessResponse[ExecutionApproval]:
    """Fetch a single approval. Raises ApprovalNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get(approval_id), message="Approval fetched.")


@router.post(
    "/{approval_id}/approve", response_model=SuccessResponse[ExecutionApproval], summary="Approve an approval"
)
async def approve_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    service: ApprovalService = Depends(get_approval_service),
) -> SuccessResponse[ExecutionApproval]:
    """Approve a PENDING approval. Raises ApprovalAlreadyDecidedError (409) otherwise.

    Does not resume execution by itself — call
    ``POST /approvals/plan/{plan_id}/resume`` next.
    """
    return SuccessResponse.ok(data=service.approve(approval_id, approver=request.approver), message="Approved.")


@router.post(
    "/{approval_id}/reject", response_model=SuccessResponse[ExecutionApproval], summary="Reject an approval"
)
async def reject_approval(
    approval_id: str,
    request: ApprovalRejectionRequest,
    service: ApprovalService = Depends(get_approval_service),
) -> SuccessResponse[ExecutionApproval]:
    """Reject a PENDING approval. Raises ApprovalAlreadyDecidedError (409) otherwise.

    Does not fail the plan by itself — call
    ``POST /approvals/plan/{plan_id}/cancel`` (or reject via the plan's
    own executor, see ``PlanningService.reject_execution()``) next.
    """
    return SuccessResponse.ok(
        data=service.reject(approval_id, approver=request.approver, reason=request.reason), message="Rejected."
    )


@router.get(
    "/plan/{plan_id}", response_model=SuccessResponse[list[ExecutionApproval]], summary="List a plan's approvals"
)
async def list_approvals_for_plan(
    plan_id: str, service: ApprovalService = Depends(get_approval_service)
) -> SuccessResponse[list[ExecutionApproval]]:
    """Every approval ever requested for a plan, most recently requested first."""
    return SuccessResponse.ok(data=service.list_for_plan(plan_id), message="Plan approvals fetched.")


@router.get(
    "/plan/{plan_id}/history",
    response_model=SuccessResponse[list[ExecutionHistoryEvent]],
    summary="Get a plan's HITL execution history",
)
async def get_plan_history(
    plan_id: str, service: ApprovalService = Depends(get_approval_service)
) -> SuccessResponse[list[ExecutionHistoryEvent]]:
    """A plan's full waiting/approved/rejected/resumed/cancelled/completed timeline, oldest first."""
    return SuccessResponse.ok(data=service.history_for_plan(plan_id), message="Plan history fetched.")


@router.post(
    "/plan/{plan_id}/resume", response_model=SuccessResponse[ExecutionPlan], summary="Resume a paused plan"
)
async def resume_plan_execution(
    plan_id: str, service: PlanningService = Depends(get_planning_service)
) -> SuccessResponse[ExecutionPlan]:
    """Resume a plan's PAUSED execution. Raises PlanNotPausedError (409) if it isn't paused.

    Safe to call after approving the pending gate — if a plan needs
    several approvals, it will pause again at the next one, and this
    endpoint is called again after that one is approved too.
    """
    plan = await service.resume_execution(plan_id)
    message = "Plan execution resumed and completed." if plan.status.value == "completed" else "Plan paused again."
    return SuccessResponse.ok(data=plan, message=message)


@router.post(
    "/plan/{plan_id}/reject", response_model=SuccessResponse[ExecutionPlan], summary="Reject a paused plan's execution"
)
async def reject_plan_execution(
    plan_id: str,
    request: ApprovalRejectionRequest,
    service: PlanningService = Depends(get_planning_service),
) -> SuccessResponse[ExecutionPlan]:
    """Reject a plan's PAUSED execution outright — it can never resume from here."""
    return SuccessResponse.ok(data=service.reject_execution(plan_id, reason=request.reason), message="Plan rejected.")


@router.post(
    "/plan/{plan_id}/cancel", response_model=SuccessResponse[ExecutionPlan], summary="Cancel a plan's execution"
)
async def cancel_plan_execution(
    plan_id: str, service: PlanningService = Depends(get_planning_service)
) -> SuccessResponse[ExecutionPlan]:
    """Cancel a plan's PAUSED (or still-RUNNING) execution outright."""
    return SuccessResponse.ok(data=service.cancel_execution(plan_id), message="Plan cancelled.")
