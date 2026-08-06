"""Execution tests: PlannerAgentNode adapting InsightPilotState <-> PlannerAgentService.

Mirrors test_report_agent_node.py. Unit-level — no GraphBuilder/
ExecutionEngine involved (see test_planner_agent_graph.py for the full
graph-level integration).
"""

import asyncio

from backend.agents.planner.execution.planner_agent import PlannerAgent
from backend.agents.planner.services.execution_result_store import (
    PlannerAgentResultStore,
)
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.nodes.planner_agent_node import PlannerAgentNode
from backend.orchestration.state.state import InsightPilotState
from backend.services.ai_service import AIService
from backend.services.planner_service import PlannerService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from config.settings import Settings


class _StubAgentNode(OrchestrationNode):
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _make_node(builder: GraphBuilder | None = None) -> PlannerAgentNode:
    builder = builder if builder is not None else GraphBuilder()
    if not builder.export().nodes:
        builder.add_node(_StubAgentNode("file_agent"))
    settings = Settings(ai_default_provider="mock", ai_default_model="mock-model")
    ai_service = AIService(ProviderFactory(settings), settings)
    planner_service = PlannerService(ai_service, PromptManager())
    planner_agent_service = PlannerAgentService(
        PlannerAgent(planner_service, builder), PlannerAgentResultStore()
    )
    return PlannerAgentNode(planner_agent_service)


def _new_state(**overrides: object) -> InsightPilotState:
    now = utc_now()
    defaults: dict[str, object] = {
        "execution_id": generate_id(),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_execute_reads_user_request_from_top_level_state_field() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1", user_request="Please clean my uploaded customer records dataset."
        )

        updated = await node.execute(state)

        result = updated.artifacts["planner_agent_result"]
        assert result["status"] == "completed"
        assert result["planner_output"]["goal"]
        assert updated.current_node == "planner"
        assert updated.execution_trace == ["planner"]
        assert updated.errors == []

    asyncio.run(scenario())


def test_execute_prefers_user_request_from_state_variables_when_present() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            user_request="This should be overridden.",
            variables={"user_request": "Please clean my uploaded customer records dataset."},
        )

        updated = await node.execute(state)

        result = updated.artifacts["planner_agent_result"]
        assert result["status"] == "completed"
        assert "clean" in result["planner_output"]["goal"].lower()

    asyncio.run(scenario())


def test_execute_passes_through_optional_planning_hints_from_variables() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={
                "user_request": "Please clean my uploaded customer records dataset.",
                "conversation_summary": "User previously uploaded a CSV.",
                "existing_reports": ["Q1 Report"],
            },
        )

        updated = await node.execute(state)

        result = updated.artifacts["planner_agent_result"]
        assert result["status"] == "completed"

    asyncio.run(scenario())


def test_execute_reports_failed_and_never_raises_when_user_request_is_missing() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(session_id="sess-1")  # no user_request anywhere

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["planner_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors
        assert updated.current_node == "planner"

    asyncio.run(scenario())


def test_execute_uses_step_id_from_state_metadata_when_present() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            user_request="Please clean my uploaded customer records dataset.",
            metadata={"step_id": "my-step-42"},
        )

        updated = await node.execute(state)

        assert updated.artifacts["planner_agent_result"]["step_id"] == "my-step-42"

    asyncio.run(scenario())


def test_execute_preserves_prior_artifacts_and_execution_trace() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            user_request="Please clean my uploaded customer records dataset.",
            artifacts={"earlier": "value"},
            execution_trace=[],
        )

        updated = await node.execute(state)

        assert updated.artifacts["earlier"] == "value"
        assert updated.execution_trace == ["planner"]

    asyncio.run(scenario())
