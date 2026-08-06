"""Unit tests for ApprovalService and ApprovalPolicyService: lifecycle, history, and
policy configuration in isolation from PlanExecutor/orchestration.
"""

import pytest

from backend.approval.exceptions import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
)
from backend.approval.models.approval import ApprovalStatus
from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore


def _make_service() -> ApprovalService:
    return ApprovalService(ApprovalStore(), ExecutionHistoryStore())


def test_request_approval_creates_a_pending_approval_and_a_waiting_history_event() -> None:
    service = _make_service()

    approval = service.request_approval("plan-1", "step-1", "sql_agent", "exec-1", reason="Policy requires it.")

    assert approval.status == ApprovalStatus.PENDING
    assert approval.plan_id == "plan-1"
    assert approval.step_id == "step-1"
    assert approval.metadata == {"node_name": "sql_agent", "execution_id": "exec-1"}
    assert approval.reason == "Policy requires it."

    history = service.history_for_plan("plan-1")
    assert len(history) == 1
    assert history[0].event_type.value == "waiting"
    assert history[0].approval_id == approval.approval_id


def test_approve_transitions_status_and_records_history() -> None:
    service = _make_service()
    approval = service.request_approval("plan-1", "step-1", "sql_agent", "exec-1")

    approved = service.approve(approval.approval_id, approver="alice")

    assert approved.status == ApprovalStatus.APPROVED
    assert approved.approver == "alice"
    assert approved.approved_at is not None
    assert service.get(approval.approval_id).status == ApprovalStatus.APPROVED
    event_types = [e.event_type.value for e in service.history_for_plan("plan-1")]
    assert event_types == ["waiting", "approved"]


def test_reject_transitions_status_and_records_reason() -> None:
    service = _make_service()
    approval = service.request_approval("plan-1", "step-1", "sql_agent", "exec-1")

    rejected = service.reject(approval.approval_id, approver="alice", reason="Too risky.")

    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.reason == "Too risky."
    event_types = [e.event_type.value for e in service.history_for_plan("plan-1")]
    assert event_types == ["waiting", "rejected"]


def test_approving_a_non_pending_approval_raises() -> None:
    service = _make_service()
    approval = service.request_approval("plan-1", "step-1", "sql_agent", "exec-1")
    service.approve(approval.approval_id)

    with pytest.raises(ApprovalAlreadyDecidedError):
        service.approve(approval.approval_id)
    with pytest.raises(ApprovalAlreadyDecidedError):
        service.reject(approval.approval_id)


def test_get_raises_for_an_unknown_approval_id() -> None:
    service = _make_service()
    with pytest.raises(ApprovalNotFoundError):
        service.get("does-not-exist")


def test_list_pending_excludes_decided_approvals() -> None:
    service = _make_service()
    pending = service.request_approval("plan-1", "step-1", "sql_agent", "exec-1")
    decided = service.request_approval("plan-1", "step-2", "browser_agent", "exec-2")
    service.approve(decided.approval_id)

    pending_ids = {a.approval_id for a in service.list_pending()}
    assert pending_ids == {pending.approval_id}


def test_list_for_plan_returns_every_approval_regardless_of_status() -> None:
    service = _make_service()
    a1 = service.request_approval("plan-1", "step-1", "sql_agent", "exec-1")
    a2 = service.request_approval("plan-1", "step-2", "browser_agent", "exec-2")
    service.approve(a2.approval_id)

    ids = {a.approval_id for a in service.list_for_plan("plan-1")}
    assert ids == {a1.approval_id, a2.approval_id}


def test_record_resumed_cancelled_completed_append_history_without_an_approval() -> None:
    service = _make_service()

    service.record_resumed("plan-1", step_id="step-1")
    service.record_cancelled("plan-1", step_id="step-1")
    service.record_completed("plan-1")

    event_types = [e.event_type.value for e in service.history_for_plan("plan-1")]
    assert event_types == ["resumed", "cancelled", "completed"]


def test_approval_policy_service_defaults_to_never_and_is_configurable() -> None:
    service = ApprovalPolicyService()
    assert service.get_policy().policy_type == ApprovalPolicyType.NEVER
    assert service.requires_approval("sql_agent") is False

    service.set_policy(ApprovalPolicy(policy_type=ApprovalPolicyType.ON_SQL))

    assert service.get_policy().policy_type == ApprovalPolicyType.ON_SQL
    assert service.requires_approval("sql_agent") is True
    assert service.requires_approval("browser_agent") is False
