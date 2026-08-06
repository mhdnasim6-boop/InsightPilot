"""Tests for WorkflowBuilder, WorkflowValidator, and WorkflowOptimizer —
all built against a real (minimal) orchestration graph and real
Adaptive/Planning services, no mocking of the collaborators they wrap.
"""

import asyncio
from pathlib import Path

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
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
from backend.planning.models.enums import PlanStatus
from backend.planning.optimizer.default import DefaultPlanOptimizer
from backend.planning.validator.validator import PlanValidator
from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.reflection.services.reflection_service import ReflectionService
from backend.services.ai_service import AIService
from backend.services.orchestration_service import OrchestrationService
from backend.services.planner_service import PlannerService
from backend.services.planning_service import PlanningService
from backend.tools.registry.tool_registry import ToolRegistry
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.models.workflow_step import WorkflowStep
from backend.workflows.planner.workflow_builder import (
    WorkflowBuilder,
    build_execution_plan,
)
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator
from config.settings import Settings


class _FakeAgentNode(OrchestrationNode):
    """A minimal, real OrchestrationNode — ``name`` is set per-instance so one
    GraphBuilder can register several under MockProvider's own canned example
    plan's node names (its response echoes the prompt template's embedded
    worked example verbatim, which references more than one real agent name)."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _harness() -> tuple[WorkflowDispatcher, PlanningService, AdaptivePlanningService, PlannerService]:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode("file_agent"))
    graph_builder.add_node(_FakeAgentNode("executive_summary_agent"))
    graph_builder.set_entry_point("file_agent")
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

    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    planner_service = PlannerService(
        ai_service, PromptManager(), memory_service=memory_service, adaptive_planning_service=adaptive_planning_service,
    )
    return dispatcher, planning_service, adaptive_planning_service, planner_service


def _step(step_id: str, dependencies: list[str] | None = None) -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=step_id, node_name="file_agent", dependencies=dependencies or [])


# -- WorkflowBuilder --------------------------------------------------------------------


def test_build_execution_plan_is_a_pure_structural_conversion() -> None:
    plan = build_execution_plan("p1", "Goal", [_step("a"), _step("b", ["a"])], session_id="s1")
    assert plan.plan_id == "p1"
    assert plan.goal == "Goal"
    assert [s.step_id for s in plan.steps] == ["a", "b"]
    assert plan.session_id == "s1"


def test_build_from_steps_creates_a_draft_workflow() -> None:
    dispatcher, _, _, _ = _harness()
    builder = WorkflowBuilder(dispatcher)
    workflow = builder.build_from_steps("My Workflow", "desc", [_step("a")], tags=["t1"])
    assert workflow.definition.name == "My Workflow"
    assert workflow.status.value == "draft"
    assert workflow.definition.tags == ["t1"]


def test_build_from_objective_without_planner_service_raises() -> None:
    dispatcher, _, _, _ = _harness()
    builder = WorkflowBuilder(dispatcher)

    async def scenario() -> None:
        try:
            await builder.build_from_objective("Do something")
            raise AssertionError("expected RuntimeError")
        except RuntimeError:
            pass

    asyncio.run(scenario())


def test_build_from_objective_uses_the_real_planner_agent() -> None:
    dispatcher, _, _, planner_service = _harness()
    builder = WorkflowBuilder(dispatcher, planner_service)

    async def scenario() -> None:
        workflow = await builder.build_from_objective("Analyze the uploaded dataset.", session_id="s1")
        assert workflow.definition.steps
        assert all(
            step.node_name in {"file_agent", "executive_summary_agent"} for step in workflow.definition.steps
        )

    asyncio.run(scenario())


# -- WorkflowValidator --------------------------------------------------------------------


def test_validate_structure_flags_an_empty_name() -> None:
    dispatcher, planning_service, _, _ = _harness()
    validator = WorkflowValidator(planning_service)
    workflow = WorkflowBuilder(dispatcher).build_from_steps("", "", [_step("a")])
    issues = validator.validate_structure(workflow)
    assert any("name" in issue.lower() for issue in issues)


def test_validate_structure_flags_no_steps() -> None:
    dispatcher, planning_service, _, _ = _harness()
    validator = WorkflowValidator(planning_service)
    workflow = WorkflowBuilder(dispatcher).build_from_steps("Name", "", [])
    issues = validator.validate_structure(workflow)
    assert any("step" in issue.lower() for issue in issues)


def test_validate_structure_flags_a_non_agent_step() -> None:
    dispatcher, planning_service, _, _ = _harness()
    validator = WorkflowValidator(planning_service)
    step = WorkflowStep(step_id="a", name="a", node_name="some_tool", kind="tool")
    workflow = WorkflowBuilder(dispatcher).build_from_steps("Name", "", [step])
    issues = validator.validate_structure(workflow)
    assert any("kind='tool'" in issue for issue in issues)


def test_validate_plan_delegates_to_the_real_plan_validator() -> None:
    _, planning_service, _, _ = _harness()
    validator = WorkflowValidator(planning_service)
    plan = build_execution_plan("p1", "goal", [_step("a")], session_id=None)

    async def scenario() -> None:
        validated_plan, result = await validator.validate_plan(plan)
        assert result.is_valid is True
        assert validated_plan.status.value == "validated"

    asyncio.run(scenario())


def test_validate_plan_flags_an_unknown_node_name() -> None:
    _, planning_service, _, _ = _harness()
    validator = WorkflowValidator(planning_service)
    bad_step = WorkflowStep(step_id="a", name="a", node_name="totally_unknown_agent")
    plan = build_execution_plan("p1", "goal", [bad_step], session_id=None)

    async def scenario() -> None:
        _, result = await validator.validate_plan(plan)
        assert result.is_valid is False

    asyncio.run(scenario())


# -- WorkflowOptimizer --------------------------------------------------------------------


def test_adaptive_optimize_returns_an_optimization_result() -> None:
    _, planning_service, adaptive_planning_service, _ = _harness()
    optimizer = WorkflowOptimizer(adaptive_planning_service, planning_service)
    plan = build_execution_plan("p1", "goal", [_step("a")], session_id=None).model_copy(
        update={"status": PlanStatus.VALIDATED}
    )
    result = optimizer.adaptive_optimize(plan, session_id="s1")
    assert result.optimization_id
    assert result.optimized_plan.plan_id == "p1"


def test_structural_optimize_advances_validated_to_ready() -> None:
    _, planning_service, adaptive_planning_service, _ = _harness()
    optimizer = WorkflowOptimizer(adaptive_planning_service, planning_service)
    validator = WorkflowValidator(planning_service)
    plan = build_execution_plan("p1", "goal", [_step("a")], session_id=None)

    async def scenario() -> None:
        validated_plan, _ = await validator.validate_plan(plan)
        ready_plan = optimizer.structural_optimize(validated_plan)
        assert ready_plan.status.value == "ready"

    asyncio.run(scenario())
