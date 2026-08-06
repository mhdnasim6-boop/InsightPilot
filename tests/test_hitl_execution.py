"""End-to-end Human-in-the-Loop tests: a plan genuinely pauses, waits for a real
approval decision, and resumes — against the real default graph, real
LangGraph checkpointer, real (MockProvider-backed) agents, no test doubles
for the orchestration/approval machinery itself.
"""

import asyncio
from pathlib import Path

import pytest

from backend.approval.exceptions import ApprovalAlreadyDecidedError
from backend.approval.policies.approval_policy import ApprovalPolicy, ApprovalPolicyType
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.planning.events.bus import PlanEventBus
from backend.planning.exceptions.errors import PlanNotPausedError
from backend.planning.executor.executor import PlanExecutor
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from tests.helpers import make_orchestration_service

_CSV_CONTENT = "date,region,revenue,cost\n2024-01-01,East,1000,600\n2024-02-01,West,200,120\n"


def _make_executor(policy_type: ApprovalPolicyType) -> tuple[PlanExecutor, ApprovalService]:
    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
    policy_service = ApprovalPolicyService(ApprovalPolicy(policy_type=policy_type))
    executor = PlanExecutor(PlanEventBus(), approval_service, policy_service)
    return executor, approval_service


def _make_plan(csv_path: Path, step_id: str = "s1") -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(
        plan_id=generate_id(),
        session_id="sess-1",
        user_request="Please clean my uploaded customer records dataset.",
        goal="Clean the dataset.",
        status=PlanStatus.READY,
        steps=[
            ExecutionStep(
                step_id=step_id,
                name="File Agent Run",
                node_name="file_agent",
                inputs={"dataset_reference": str(csv_path)},
            )
        ],
        created_at=now,
        updated_at=now,
    )


def test_never_policy_never_pauses(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.NEVER)
        orchestration_service = make_orchestration_service()

        result = await executor.execute(_make_plan(csv_file), orchestration_service)

        assert result.status == PlanStatus.COMPLETED
        assert approval_service.list_pending() == []

    asyncio.run(scenario())


def test_always_policy_pauses_before_the_first_gated_agent(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.ALWAYS)
        orchestration_service = make_orchestration_service()

        result = await executor.execute(_make_plan(csv_file), orchestration_service)

        assert result.status == PlanStatus.PAUSED
        pending = approval_service.list_pending()
        assert len(pending) == 1
        assert pending[0].metadata["node_name"] == "file_agent"
        assert pending[0].plan_id == result.plan_id

    asyncio.run(scenario())


def test_on_sql_policy_only_pauses_before_sql_not_file(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.ON_SQL)
        orchestration_service = make_orchestration_service()

        result = await executor.execute(_make_plan(csv_file), orchestration_service)

        # FileAgent runs straight through; the graph reaches sql_agent next
        # (every plan step still triggers the whole linear graph) and pauses there.
        assert result.status == PlanStatus.PAUSED
        pending = approval_service.list_pending()
        assert len(pending) == 1
        assert pending[0].metadata["node_name"] == "sql_agent"

    asyncio.run(scenario())


def test_approve_then_resume_completes_the_plan(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.ALWAYS)
        orchestration_service = make_orchestration_service()

        paused = await executor.execute(_make_plan(csv_file), orchestration_service)
        assert paused.status == PlanStatus.PAUSED

        # Every one of the five gates needs a decision under ALWAYS - approve
        # and resume until the plan genuinely completes.
        plan_id = paused.plan_id
        current = paused
        approvals_seen = 0
        while current.status == PlanStatus.PAUSED:
            pending = approval_service.list_pending()
            assert pending, "expected a pending approval while the plan is paused"
            approval_service.approve(pending[0].approval_id, approver="qa")
            approvals_seen += 1
            current = await executor.resume(plan_id, orchestration_service)
            assert approvals_seen <= 10  # safety valve against an infinite loop bug

        assert current.status == PlanStatus.COMPLETED
        assert approvals_seen == 5  # one gate per real agent
        assert approval_service.list_pending() == []

        history = approval_service.history_for_plan(plan_id)
        event_types = [event.event_type.value for event in history]
        assert event_types.count("waiting") == 5
        assert event_types.count("approved") == 5
        assert event_types.count("resumed") == 5
        assert event_types.count("completed") == 1

    asyncio.run(scenario())


def test_reject_fails_the_plan_and_it_cannot_be_resumed(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.ALWAYS)
        orchestration_service = make_orchestration_service()

        paused = await executor.execute(_make_plan(csv_file), orchestration_service)
        assert paused.status == PlanStatus.PAUSED
        pending = approval_service.list_pending()[0]

        approval_service.reject(pending.approval_id, approver="qa", reason="Not today.")
        rejected_plan = executor.reject(paused.plan_id, reason="Not today.")

        assert rejected_plan.status == PlanStatus.FAILED
        assert rejected_plan.metadata["rejection_reason"] == "Not today."
        with pytest.raises(PlanNotPausedError):
            await executor.resume(paused.plan_id, orchestration_service)

    asyncio.run(scenario())


def test_cancel_a_paused_plan(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.ALWAYS)
        orchestration_service = make_orchestration_service()

        paused = await executor.execute(_make_plan(csv_file), orchestration_service)
        assert paused.status == PlanStatus.PAUSED

        cancelled = executor.cancel(paused.plan_id, orchestration_service)

        assert cancelled.status == PlanStatus.CANCELLED
        with pytest.raises(PlanNotPausedError):
            await executor.resume(paused.plan_id, orchestration_service)
        history = approval_service.history_for_plan(paused.plan_id)
        assert any(event.event_type.value == "cancelled" for event in history)

    asyncio.run(scenario())


def test_approving_an_already_decided_approval_raises(tmp_path: Path) -> None:
    async def scenario() -> None:
        csv_file = tmp_path / "sales.csv"
        csv_file.write_text(_CSV_CONTENT)
        executor, approval_service = _make_executor(ApprovalPolicyType.ALWAYS)
        orchestration_service = make_orchestration_service()

        paused = await executor.execute(_make_plan(csv_file), orchestration_service)
        pending = approval_service.list_pending()[0]
        approval_service.approve(pending.approval_id, approver="qa")

        with pytest.raises(ApprovalAlreadyDecidedError):
            approval_service.approve(pending.approval_id, approver="qa")

        assert paused.status == PlanStatus.PAUSED  # unrelated to the exception above

    asyncio.run(scenario())


def test_resuming_a_plan_that_was_never_paused_raises() -> None:
    async def scenario() -> None:
        executor, _ = _make_executor(ApprovalPolicyType.NEVER)
        orchestration_service = make_orchestration_service()
        with pytest.raises(PlanNotPausedError):
            await executor.resume("never-ran", orchestration_service)

    asyncio.run(scenario())
