"""Execution tests: PlannerAgent adapting an ExecutionStep <-> PlannerService, with
dynamic agent discovery read live off a GraphBuilder — no external AI (MockProvider).

Unit-level — no ExecutionEngine/full default graph involved (see
test_planner_agent_graph.py for the full graph-level integration, and
test_planner_agent_node.py for the InsightPilotState adapter).
"""

import asyncio

import pytest

from backend.agents.planner.exceptions import InvalidPlannerAgentInputError
from backend.agents.planner.execution.planner_agent import PlannerAgent
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.services.ai_service import AIService
from backend.services.planner_service import PlannerService
from config.settings import Settings


class _StubAgentNode(OrchestrationNode):
    """A minimal registered node with its own metadata(), for discovery tests."""

    def __init__(self, name: str, description: str | None = None) -> None:
        self.name = name
        self._description = description

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state

    def metadata(self) -> dict[str, object]:
        base = super().metadata()
        if self._description:
            base["description"] = self._description
        return base


def _make_planner_agent(builder: GraphBuilder) -> PlannerAgent:
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    planner_service = PlannerService(ai_service, PromptManager())
    return PlannerAgent(planner_service, builder)


def _register_all_five_agents(builder: GraphBuilder) -> None:
    for name, description in [
        ("file_agent", "Ingests a file."),
        ("sql_agent", "Imports a table."),
        ("browser_agent", "Gathers external context."),
        ("report_agent", "Builds a report."),
        ("executive_summary_agent", "Writes a summary."),
    ]:
        builder.add_node(_StubAgentNode(name, description))


def test_execute_produces_a_completed_result_with_a_real_plan() -> None:
    async def scenario() -> None:
        builder = GraphBuilder()
        _register_all_five_agents(builder)
        agent = _make_planner_agent(builder)
        step = ExecutionStep(
            step_id="s1",
            name="Planner Agent Run",
            node_name="planner",
            inputs={"user_request": "Generate a business report."},
        )

        result = await agent.execute(step, "sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert result.warnings == []
        assert result.planner_output is not None
        assert result.planner_output.goal
        assert len(result.planner_output.execution_plan.steps) > 0

    asyncio.run(scenario())


def test_execute_discovers_only_currently_registered_agent_nodes() -> None:
    """Never a hardcoded agent list — reflects whatever is registered on the builder
    at call time, excluding the infrastructure nodes (planner/router/end)."""

    async def scenario() -> None:
        builder = GraphBuilder()
        builder.add_node(_StubAgentNode("file_agent", "Ingests a file."))
        builder.add_node(_StubAgentNode("planner"))
        builder.add_node(_StubAgentNode("end"))
        agent = _make_planner_agent(builder)
        step = ExecutionStep(
            step_id="s2",
            name="Planner Agent Run",
            node_name="planner",
            inputs={"user_request": "Please clean my uploaded customer records dataset."},
        )

        result = await agent.execute(step, "sess-1")

        assert result.metadata["available_services"] == ["file_agent"]
        assert all(step_draft.node_name == "file_agent" for step_draft in result.planner_output.execution_plan.steps)

    asyncio.run(scenario())


def test_execute_reflects_newly_added_nodes_on_the_same_builder_without_reconstruction() -> None:
    """Proves discovery is genuinely dynamic: adding a node to ``builder`` after
    PlannerAgent is constructed still shows up on the next call — no caching."""

    async def scenario() -> None:
        builder = GraphBuilder()
        builder.add_node(_StubAgentNode("file_agent", "Ingests a file."))
        agent = _make_planner_agent(builder)

        clean_request = "Please clean my uploaded customer records dataset."
        first = await agent.execute(
            ExecutionStep(step_id="s3a", name="x", node_name="planner", inputs={"user_request": clean_request}),
            "sess-1",
        )
        assert first.metadata["available_services"] == ["file_agent"]

        builder.add_node(_StubAgentNode("sql_agent", "Imports a table."))

        second = await agent.execute(
            ExecutionStep(step_id="s3b", name="x", node_name="planner", inputs={"user_request": clean_request}),
            "sess-1",
        )
        assert set(second.metadata["available_services"]) == {"file_agent", "sql_agent"}

    asyncio.run(scenario())


def test_execute_raises_invalid_input_error_for_missing_user_request() -> None:
    async def scenario() -> None:
        builder = GraphBuilder()
        _register_all_five_agents(builder)
        agent = _make_planner_agent(builder)
        step = ExecutionStep(step_id="s4", name="Bad", node_name="planner", inputs={})

        with pytest.raises(InvalidPlannerAgentInputError):
            await agent.execute(step, "sess-1")

    asyncio.run(scenario())


def test_execute_raises_invalid_input_error_for_blank_user_request() -> None:
    async def scenario() -> None:
        builder = GraphBuilder()
        _register_all_five_agents(builder)
        agent = _make_planner_agent(builder)
        step = ExecutionStep(step_id="s5", name="Bad", node_name="planner", inputs={"user_request": "   "})

        with pytest.raises(InvalidPlannerAgentInputError):
            await agent.execute(step, "sess-1")

    asyncio.run(scenario())


def test_execute_reports_failed_and_never_raises_when_the_plan_fails_validation() -> None:
    """Only one agent is registered, but the matched example plan references others
    -> PlanValidationFailedError inside PlannerService, captured as a FAILED result."""

    async def scenario() -> None:
        builder = GraphBuilder()
        builder.add_node(_StubAgentNode("executive_summary_agent"))
        agent = _make_planner_agent(builder)
        step = ExecutionStep(
            step_id="s6",
            name="Planner Agent Run",
            node_name="planner",
            inputs={"user_request": "Generate a business report."},
        )

        result = await agent.execute(step, "sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert result.planner_output is None
        assert result.warnings

    asyncio.run(scenario())
