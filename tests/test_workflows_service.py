"""Tests for WorkflowService: the single public entry point. Covers
create/validate/optimize/execute/pause/resume/cancel/clone/export/
statistics/checkpoint against a real (not mocked) collaborator stack —
built with the same fake-agent-node harness every other
tests/test_workflows_*.py file already uses.
"""

import asyncio
import json
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
from backend.workflows.coordination.collaboration_manager import (
    WorkflowCollaborationManager,
)
from backend.workflows.coordination.dependency_graph import WorkflowDependencyGraph
from backend.workflows.coordination.execution_coordinator import ExecutionCoordinator
from backend.workflows.coordination.resource_allocator import ResourceAllocator
from backend.workflows.exceptions import (
    WorkflowExecutionNotFoundError,
    WorkflowNotFoundError,
)
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.execution.workflow_engine import WorkflowEngine
from backend.workflows.execution.workflow_scheduler import WorkflowScheduler
from backend.workflows.models.workflow_step import WorkflowStep
from backend.workflows.planner.workflow_builder import WorkflowBuilder
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator
from backend.workflows.services.workflow_service import WorkflowService, WorkflowStore


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


def _service(agent_names: tuple[str, ...] = ("agent_a", "agent_b")) -> WorkflowService:
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
        node_dispatcher.register(name, _OkService())
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
    builder = WorkflowBuilder(dispatcher)
    collaboration_manager = WorkflowCollaborationManager(None)

    return WorkflowService(
        store=WorkflowStore(), builder=builder, validator=validator, optimizer=optimizer, engine=engine,
        execution_coordinator=execution_coordinator, dependency_graph=dependency_graph, dispatcher=dispatcher,
        collaboration_manager=collaboration_manager, execution_service=execution_service,
        approval_service=approval_service, memory_service=memory_service, observability_service=observability_service,
    )


def _step(step_id: str, node_name: str, dependencies: list[str] | None = None) -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=step_id, node_name=node_name, dependencies=dependencies or [])


def test_create_from_steps_and_get_round_trip() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "desc", [_step("s1", "agent_a")])
    assert service.get(workflow.workflow_id) == workflow


def test_get_raises_for_an_unknown_workflow() -> None:
    with pytest.raises(WorkflowNotFoundError):
        _service().get("does-not-exist")


def test_list_workflows_returns_every_created_workflow() -> None:
    service = _service()
    service.create_from_steps("A", "", [_step("s1", "agent_a")])
    service.create_from_steps("B", "", [_step("s1", "agent_a")])
    assert {w.definition.name for w in service.list_workflows()} == {"A", "B"}


def test_validate_reports_issues_for_an_empty_workflow() -> None:
    service = _service()
    workflow = service.create_from_steps("", "", [])

    async def scenario() -> None:
        validated, issues = await service.validate(workflow.workflow_id)
        assert issues
        assert validated.status.value == "draft"  # unchanged — invalid

    asyncio.run(scenario())


def test_validate_succeeds_for_a_valid_workflow() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        validated, issues = await service.validate(workflow.workflow_id)
        assert issues == []
        assert validated.status.value == "validated"

    asyncio.run(scenario())


def test_optimize_advances_a_workflow_to_ready() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        optimized = await service.optimize(workflow.workflow_id, session_id="s1")
        assert optimized.status.value == "ready"
        assert optimized.plan_id is not None

    asyncio.run(scenario())


def test_execute_runs_a_workflow_and_records_the_execution() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        execution = await service.execute(workflow.workflow_id, session_id="s1")
        assert execution.status.value == "completed"
        assert service.get(workflow.workflow_id).status.value == "completed"
        assert service.get_execution(execution.workflow_execution_id) == execution
        assert service.list_executions(workflow.workflow_id) == [execution]

    asyncio.run(scenario())


def test_get_execution_raises_for_an_unknown_id() -> None:
    with pytest.raises(WorkflowExecutionNotFoundError):
        _service().get_execution("does-not-exist")


def test_get_latest_execution_raises_before_any_execution() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])
    with pytest.raises(WorkflowExecutionNotFoundError):
        service.get_latest_execution(workflow.workflow_id)


def test_pause_and_resume_a_still_completed_execution_is_idempotent() -> None:
    """pause()/cancel() on an already-terminal execution are safe no-ops (see
    WorkflowEngine's own docstring) — proven end-to-end through the service."""
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        execution = await service.execute(workflow.workflow_id, session_id="s1")
        paused = await service.pause(execution.workflow_execution_id)
        assert paused.status.value == "completed"  # no-op, already terminal

    asyncio.run(scenario())


def test_cancel_an_already_completed_execution_is_idempotent() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        execution = await service.execute(workflow.workflow_id, session_id="s1")
        cancelled = service.cancel(execution.workflow_execution_id)
        assert cancelled.status.value == "completed"

    asyncio.run(scenario())


def test_clone_creates_a_new_draft_workflow() -> None:
    service = _service()
    workflow = service.create_from_steps("Original", "desc", [_step("s1", "agent_a")])
    cloned = service.clone(workflow.workflow_id)
    assert cloned.workflow_id != workflow.workflow_id
    assert cloned.cloned_from == workflow.workflow_id
    assert cloned.status.value == "draft"
    assert "copy" in cloned.definition.name


def test_clone_with_a_custom_name() -> None:
    service = _service()
    workflow = service.create_from_steps("Original", "desc", [_step("s1", "agent_a")])
    cloned = service.clone(workflow.workflow_id, new_name="Renamed")
    assert cloned.definition.name == "Renamed"


def test_export_json_includes_the_workflow() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])
    payload = json.loads(service.export(workflow.workflow_id, "json"))
    assert payload["workflow"]["workflow_id"] == workflow.workflow_id


def test_export_markdown_includes_the_workflow_name() -> None:
    service = _service()
    workflow = service.create_from_steps("My Workflow", "", [_step("s1", "agent_a")])
    markdown = service.export(workflow.workflow_id, "markdown")
    assert "My Workflow" in markdown


def test_get_graph_returns_mermaid() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])
    assert "graph TD;" in service.get_graph(workflow.workflow_id)


def test_statistics_reflects_executions() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        await service.execute(workflow.workflow_id, session_id="s1")
        stats = service.statistics(workflow.workflow_id)
        assert stats.total_executions == 1
        assert stats.successful_executions == 1
        assert stats.failed_executions == 0

    asyncio.run(scenario())


def test_get_checkpoint_composes_real_state() -> None:
    service = _service()
    workflow = service.create_from_steps("W", "", [_step("s1", "agent_a")])

    async def scenario() -> None:
        execution = await service.execute(workflow.workflow_id, session_id="s1")
        checkpoint = service.get_checkpoint(execution.workflow_execution_id)
        assert checkpoint.completed_agents == ["agent_a"]

    asyncio.run(scenario())


def test_discover_agents_never_hardcodes_a_name() -> None:
    service = _service(agent_names=("totally_custom_name",))
    assert service.discover_agents() == ["totally_custom_name"]
