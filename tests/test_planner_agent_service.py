"""Unit tests for PlannerAgentService: stores results, fetches them back, lists them.

Mirrors test_report_agent_service.py's shape (if present) / the same
store-then-fetch contract every other agent's own service has.
"""

import asyncio

import pytest

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.agents.planner.execution.planner_agent import PlannerAgent
from backend.agents.planner.services.execution_result_store import (
    PlannerAgentResultStore,
)
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.services.ai_service import AIService
from backend.services.planner_service import PlannerService
from config.settings import Settings


class _StubAgentNode(OrchestrationNode):
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _make_service() -> PlannerAgentService:
    builder = GraphBuilder()
    builder.add_node(_StubAgentNode("file_agent"))
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    planner_service = PlannerService(ai_service, PromptManager())
    return PlannerAgentService(PlannerAgent(planner_service, builder), PlannerAgentResultStore())


def test_execute_step_stores_the_result_and_returns_it() -> None:
    async def scenario() -> None:
        service = _make_service()
        step = ExecutionStep(
            step_id="svc-1",
            name="Planner Agent Run",
            node_name="planner",
            inputs={"user_request": "Please clean my uploaded customer records dataset."},
        )

        result = await service.execute_step(step, "sess-1")

        assert result.status.value == "completed"
        assert service.get_result("svc-1") is result

    asyncio.run(scenario())


def test_get_result_raises_agent_execution_not_found_error_for_unknown_step() -> None:
    service = _make_service()
    with pytest.raises(AgentExecutionNotFoundError):
        service.get_result("never-ran")


def test_list_results_returns_every_stored_result_most_recent_first() -> None:
    async def scenario() -> None:
        service = _make_service()
        for step_id in ("svc-a", "svc-b"):
            step = ExecutionStep(
                step_id=step_id,
                name="Planner Agent Run",
                node_name="planner",
                inputs={"user_request": "Please clean my uploaded customer records dataset."},
            )
            await service.execute_step(step, "sess-1")

        results = service.list_results()

        assert [result.step_id for result in results] == ["svc-b", "svc-a"]

    asyncio.run(scenario())
