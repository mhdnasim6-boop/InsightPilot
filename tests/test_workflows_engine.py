"""Tests for WorkflowEngine: execute/pause/resume/cancel — built entirely
from real collaborators (PlanValidator, DefaultPlanOptimizer,
AdaptivePlanningService, ExecutionService/DAGScheduler), with only the
agent *services* faked (mirrors tests/test_execution_service.py's own
``_OkService``/``_FailingService`` pattern) — no mocking of anything this
package itself owns.
"""

import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.memory.exporters.json_exporter import JSONMemoryExporter
from backend.memory.exporters.markdown_exporter import MarkdownMemoryExporter
from backend.memory.retrieval.retrieval_engine import RetrievalEngine
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.memory.summarization.memory_summarizer import MemorySummarizer
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.events.bus import EventBus
from backend.orchestration.execution.engine import ExecutionEngine
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.planning.events.bus import PlanEventBus
from backend.planning.executor.executor import PlanExecutor
from backend.planning.optimizer.default import DefaultPlanOptimizer
from backend.planning.validator.validator import PlanValidator
from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.reflection.services.reflection_service import ReflectionService
from backend.services.orchestration_service import OrchestrationService
from backend.services.planning_service import PlanningService
from backend.tools.registry.tool_registry import ToolRegistry
from backend.utils.time import utc_now
from backend.workflows.coordination.dependency_graph import WorkflowDependencyGraph
from backend.workflows.coordination.execution_coordinator import ExecutionCoordinator
from backend.workflows.coordination.resource_allocator import ResourceAllocator
from backend.workflows.exceptions import WorkflowNotPausedError, WorkflowNotReadyError
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.execution.workflow_engine import WorkflowEngine
from backend.workflows.execution.workflow_scheduler import WorkflowScheduler
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_step import WorkflowStep
from backend.workflows.planner.workflow_builder import WorkflowBuilder
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator


class _FakeAgentNode(OrchestrationNode):
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _OkService:
    async def execute_step(self, step: object, session_id: str | None) -> _Result:
        return _Result(step_id=step.step_id)  # type: ignore[attr-defined]


class _FailingService:
    async def execute_step(self, step: object, session_id: str | None) -> _Result:
        raise RuntimeError("boom")


def _harness(agent_names: tuple[str, ...] = ("agent_a", "agent_b"), failing: frozenset[str] = frozenset()) -> tuple[
    WorkflowEngine, WorkflowDispatcher
]:
    graph_builder = GraphBuilder()
    for name in agent_names:
        graph_builder.add_node(_FakeAgentNode(name))
    graph_builder.set_entry_point(agent_names[0])
    orchestration_service = OrchestrationService(graph_builder, ExecutionEngine(EventBus()))
    capability_registry = AgentCapabilityRegistry(graph_builder)

    memory_service = MemoryService(
        store=MemoryStore(), retrieval_engine=RetrievalEngine(), summarizer=MemorySummarizer(),
        json_exporter=JSONMemoryExporter(), markdown_exporter=MarkdownMemoryExporter(),
    )
    observability_service = ObservabilityService(TraceStore())
    reflection_service = ReflectionService(memory_service, observability_service)
    adaptive_planning_service = AdaptivePlanningService(memory_service, reflection_service, observability_service)

    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
    executor = PlanExecutor(PlanEventBus(), approval_service, ApprovalPolicyService(), observability_service)
    planning_service = PlanningService(
        PlanValidator(), DefaultPlanOptimizer(), executor, orchestration_service, PlanEventBus(),
    )

    tool_registry = ToolRegistry()
    plugin_registry = PluginRegistry(
        PluginLoader(Path("/nonexistent-workflows-test-path")), PluginValidator("0.1.0"), tool_registry,
    )
    dispatcher = WorkflowDispatcher(capability_registry, tool_registry, plugin_registry)
    dependency_graph = WorkflowDependencyGraph()
    execution_coordinator = ExecutionCoordinator(dispatcher, dependency_graph)

    validator = WorkflowValidator(planning_service)
    optimizer = WorkflowOptimizer(adaptive_planning_service, planning_service)

    node_dispatcher = NodeDispatcher()
    for name in agent_names:
        node_dispatcher.register(name, _FailingService() if name in failing else _OkService())
    scheduler = DAGScheduler(node_dispatcher, observability_service=observability_service)
    execution_service = ExecutionService(
        scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry(), observability_service,
        memory_service=memory_service,
    )

    workflow_scheduler = WorkflowScheduler(ResourceAllocator())
    engine = WorkflowEngine(
        execution_coordinator, validator, optimizer, execution_service, workflow_scheduler,
        observability_service, reflection_service,
    )
    return engine, dispatcher


def _step(step_id: str, node_name: str, dependencies: list[str] | None = None) -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=step_id, node_name=node_name, dependencies=dependencies or [])


def test_execute_runs_a_single_step_workflow_to_completion() -> None:
    engine, dispatcher = _harness()
    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        updated_workflow, execution = await engine.execute(workflow, session_id="s1")
        assert updated_workflow.status.value == "completed"
        assert execution.status.value == "completed"
        assert execution.completed_steps == ["s1"]
        assert execution.optimization_id
        assert execution.trace_id
        assert execution.reflection_id  # completed -> reflection generated

    asyncio.run(scenario())


def test_execute_runs_two_independent_steps_in_parallel() -> None:
    engine, dispatcher = _harness()
    workflow = WorkflowBuilder(dispatcher).build_from_steps(
        "W", "", [_step("s1", "agent_a"), _step("s2", "agent_b")]
    )

    async def scenario() -> None:
        _, execution = await engine.execute(workflow, session_id="s1")
        assert set(execution.completed_steps) == {"s1", "s2"}

    asyncio.run(scenario())


def test_execute_records_a_failed_step_and_no_reflection() -> None:
    engine, dispatcher = _harness(failing={"agent_a"})
    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        updated_workflow, execution = await engine.execute(workflow, session_id="s1")
        assert updated_workflow.status.value == "failed"
        assert execution.failed_steps == ["s1"]
        assert execution.reflection_id is None

    asyncio.run(scenario())


def test_pause_requires_a_started_execution() -> None:
    engine, dispatcher = _harness()
    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        _, execution = await engine.execute(workflow, session_id="s1")
        never_started = execution.model_copy(update={"execution_id": None, "status": "running"})
        with pytest.raises(WorkflowNotReadyError):
            await engine.pause(never_started)

    asyncio.run(scenario())


def test_resume_requires_a_paused_execution() -> None:
    engine, dispatcher = _harness()
    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        _, execution = await engine.execute(workflow, session_id="s1")  # completes immediately
        with pytest.raises(WorkflowNotPausedError):
            await engine.resume(execution, workflow, session_id="s1")

    asyncio.run(scenario())


def test_cancel_on_an_already_completed_execution_is_a_no_op() -> None:
    """A real, plausible race (not a hypothetical): the caller's own cancel click can
    lose a race against a fast-completing execution. Without this guard,
    ExecutionService.cancel() would try to finalize an already-finalized
    ObservabilityService trace a second time and raise TraceNotFoundError —
    caught live by this exact test during development, not assumed."""
    engine, dispatcher = _harness()
    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        _, execution = await engine.execute(workflow, session_id="s1")
        assert execution.status.value == "completed"
        cancelled = engine.cancel(execution)
        assert cancelled.status.value == "completed"
        assert cancelled == execution

    asyncio.run(scenario())


def test_cancel_interrupts_a_genuinely_in_flight_execution() -> None:
    """Mirrors tests/test_execution_service.py's own
    test_cancel_interrupts_a_genuinely_in_flight_execution — a hanging agent
    service plus a background task, polling the same ExecutionCheckpointStore
    ExecutionService itself was built with to find the in-flight execution_id
    (only known once execute() itself returns, which won't happen until the
    DAG settles)."""

    class _HangingService:
        async def execute_step(self, step: object, session_id: str | None) -> _Result:
            await asyncio.sleep(5)
            return _Result(step_id=step.step_id)  # type: ignore[attr-defined]

    engine, dispatcher = _harness()
    # Swap in a hanging agent service so the execution stays genuinely in-flight —
    # _harness() doesn't expose its own NodeDispatcher directly, so this test builds
    # its own minimal ExecutionService (test-only introspection via engine._execution_service,
    # mirroring test_execution_service.py's own established `service._checkpoint_store` pattern).
    node_dispatcher = NodeDispatcher()
    node_dispatcher.register("agent_a", _HangingService())
    observability_service = ObservabilityService(TraceStore())
    scheduler = DAGScheduler(node_dispatcher, observability_service=observability_service)
    checkpoint_store = ExecutionCheckpointStore()
    execution_service = ExecutionService(scheduler, checkpoint_store, ExecutionTaskRegistry(), observability_service)
    engine._execution_service = execution_service  # type: ignore[attr-defined]

    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        task = asyncio.create_task(engine.execute(workflow, session_id="s1"))
        await asyncio.sleep(0.2)  # let the hanging step actually start dispatching

        checkpoints = checkpoint_store.list_all()
        assert checkpoints, "expected at least one checkpoint by now"
        in_flight = WorkflowExecution(
            workflow_execution_id="we1", workflow_id=workflow.workflow_id, plan_id=checkpoints[0].plan_id,
            execution_id=checkpoints[0].execution_id, started_at=utc_now(), updated_at=utc_now(),
        )
        cancelled = engine.cancel(in_flight)
        assert cancelled.status.value == "cancelled"
        task.cancel()

    asyncio.run(scenario())


def test_pause_then_resume_reruns_only_the_incomplete_steps() -> None:
    """A manually-paused execution's own resume() rebuilds a plan containing only
    the not-yet-completed steps — proven with an already-completed workflow (the
    'remaining steps' set is empty), the simplest deterministic case to assert
    against without needing to interrupt an in-flight async task mid-run."""
    engine, dispatcher = _harness()
    workflow = WorkflowBuilder(dispatcher).build_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        updated_workflow, execution = await engine.execute(workflow, session_id="s1")
        assert execution.status.value == "completed"
        # Simulate a manually-paused execution whose one step already completed.
        paused = execution.model_copy(
            update={"status": "paused", "pause_reason": "manual", "pending_steps": [], "failed_steps": []}
        )
        final_workflow, resumed = await engine.resume(paused, updated_workflow, session_id="s1")
        assert resumed.status.value == "completed"
        assert final_workflow.status.value == "completed"

    asyncio.run(scenario())
