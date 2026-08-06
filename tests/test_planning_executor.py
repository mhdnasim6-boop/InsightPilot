"""Tests for PlanExecutor: delegates ExecutionPlan steps to OrchestrationService (mocked)."""

import asyncio

import pytest

from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.events.bus import PlanEventBus
from backend.planning.exceptions.errors import PlanNotReadyError
from backend.planning.executor.executor import PlanExecutor
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


class _StubOrchestrationService:
    """A minimal OrchestrationService stand-in: no graph, no LangGraph — just a recorder.

    Used instead of the real service so these tests exercise PlanExecutor's
    integration contract in isolation, per the "using mocks" requirement.
    """

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[InsightPilotState] = []
        self._fail_on = fail_on

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        self.calls.append(state)
        step_id = state.metadata["step_id"]
        if self._fail_on is not None and step_id == self._fail_on:
            raise RuntimeError(f"simulated failure for step '{self._fail_on}'")
        return state.model_copy(update={"status": ExecutionStatus.COMPLETED, "artifacts": {"result": step_id}})

    async def get_next_nodes(self, execution_id: str) -> tuple[str, ...]:
        """No checkpointer, no graph — this stub never pauses (Phase 23, Human-in-the-Loop)."""
        return ()


def _step(step_id: str, dependencies: list[str] | None = None) -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name=step_id, node_name="planner", dependencies=dependencies or [])


def _ready_plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", created_at=now, updated_at=now, steps=steps, status=PlanStatus.READY)


def test_execute_rejects_a_plan_that_is_not_ready() -> None:
    async def scenario() -> None:
        executor = PlanExecutor()
        draft_plan = _ready_plan([_step("a")]).model_copy(update={"status": PlanStatus.DRAFT})

        with pytest.raises(PlanNotReadyError):
            await executor.execute(draft_plan, _StubOrchestrationService())  # type: ignore[arg-type]

    asyncio.run(scenario())


def test_execute_runs_steps_in_order_and_completes_the_plan() -> None:
    async def scenario() -> None:
        plan = _ready_plan([_step("a"), _step("b", dependencies=["a"])])
        stub = _StubOrchestrationService()
        executor = PlanExecutor()

        result = await executor.execute(plan, stub, execution_order=["a", "b"])  # type: ignore[arg-type]

        assert result.status == PlanStatus.COMPLETED
        assert [step.step_id for step in result.steps] == ["a", "b"]
        assert all(step.status == ExecutionStatus.COMPLETED for step in result.steps)
        assert [call.metadata["step_id"] for call in stub.calls] == ["a", "b"]

    asyncio.run(scenario())


def test_execute_captures_step_outputs_from_orchestration_artifacts() -> None:
    async def scenario() -> None:
        plan = _ready_plan([_step("a")])
        executor = PlanExecutor()

        result = await executor.execute(plan, _StubOrchestrationService())  # type: ignore[arg-type]

        assert result.steps[0].outputs == {"result": "a"}

    asyncio.run(scenario())


def test_execute_emits_events_in_expected_order() -> None:
    async def scenario() -> None:
        bus = PlanEventBus()
        event_names: list[str] = []
        bus.subscribe(lambda event: event_names.append(type(event).__name__))
        plan = _ready_plan([_step("a"), _step("b", dependencies=["a"])])
        executor = PlanExecutor(bus)

        await executor.execute(plan, _StubOrchestrationService(), execution_order=["a", "b"])  # type: ignore[arg-type]

        assert event_names == [
            "PlanStarted",
            "StepStarted",
            "StepCompleted",
            "StepStarted",
            "StepCompleted",
            "PlanCompleted",
        ]

    asyncio.run(scenario())


def test_execute_marks_plan_failed_and_reraises_on_step_failure() -> None:
    async def scenario() -> None:
        bus = PlanEventBus()
        event_names: list[str] = []
        bus.subscribe(lambda event: event_names.append(type(event).__name__))
        plan = _ready_plan([_step("a"), _step("b", dependencies=["a"])])
        executor = PlanExecutor(bus)
        stub = _StubOrchestrationService(fail_on="b")

        with pytest.raises(RuntimeError):
            await executor.execute(plan, stub, execution_order=["a", "b"])  # type: ignore[arg-type]

        assert event_names[-1] == "PlanFailed"
        inspected = executor.inspect(plan.plan_id)
        assert inspected is not None
        assert inspected.status == PlanStatus.FAILED

    asyncio.run(scenario())


def test_inspect_unknown_plan_returns_none() -> None:
    assert PlanExecutor().inspect("never-ran") is None
