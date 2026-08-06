"""Request bodies for the /api/v1/approvals/* endpoints."""

from pydantic import BaseModel

from backend.approval.policies.approval_policy import ApprovalPolicyType


class ApprovalDecisionRequest(BaseModel):
    """Body for approving an ExecutionApproval."""

    approver: str | None = None


class ApprovalRejectionRequest(BaseModel):
    """Body for rejecting an ExecutionApproval."""

    approver: str | None = None
    reason: str | None = None


class ApprovalPolicyRequest(BaseModel):
    """Body for configuring the active ApprovalPolicy."""

    policy_type: ApprovalPolicyType
