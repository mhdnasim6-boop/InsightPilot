"""ExecutionApproval: one human approval decision gating one paused graph node.

Immutable like every other lifecycle model in this codebase
(``ExecutionPlan``, ``InsightPilotState``) — a decision (approve/reject)
produces a new instance via ``model_copy``, never in-place mutation.
Field set is exactly what this phase specified; the gated node's name
and the paused graph execution's ``execution_id`` (needed to actually
resume it) live in ``metadata`` rather than as dedicated fields, since
both are orchestration plumbing an approver never needs to set
themselves — only read, via ``metadata["node_name"]``/
``metadata["execution_id"]``.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    """Lifecycle of one approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExecutionApproval(BaseModel):
    """One request for a human decision before a specific graph node runs."""

    model_config = ConfigDict(frozen=True)

    approval_id: str
    plan_id: str
    step_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str | None = None
    requested_at: datetime
    approved_at: datetime | None = None
    approver: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
