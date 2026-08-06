"""Execution tests: BrowserAgentNode adapting InsightPilotState <-> BrowserAgentService.

Mirrors test_file_agent_node.py/test_sql_agent_node.py. Unit-level — no
GraphBuilder/ExecutionEngine involved (see test_browser_agent_graph.py
for the full graph-level integration).
"""

import asyncio

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.browser.services.execution_result_store import (
    BrowserAgentResultStore,
)
from backend.browser.providers.mock import MockBrowserProvider
from backend.orchestration.nodes.browser_agent_node import BrowserAgentNode
from backend.orchestration.state.state import InsightPilotState
from backend.services.browser_service import BrowserService
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


def _make_node() -> BrowserAgentNode:
    agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    return BrowserAgentNode(BrowserAgentService(agent, BrowserAgentResultStore()))


def _new_state(**overrides: object) -> InsightPilotState:
    now = utc_now()
    defaults: dict[str, object] = {
        "execution_id": generate_id(),
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return InsightPilotState.model_validate(defaults)


def test_execute_reads_search_request_from_state_variables() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1", variables={"search_request": "Acme Corp"}
        )

        updated = await node.execute(state)

        result = updated.artifacts["browser_agent_result"]
        assert result["status"] == "completed"
        assert len(result["sources"]) == 3
        assert updated.current_node == "browser_agent"
        assert updated.execution_trace == ["browser_agent"]
        assert updated.errors == []

    asyncio.run(scenario())


def test_execute_uses_step_id_from_state_metadata_when_present() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"search_request": "Acme Corp"},
            metadata={"step_id": "my-step-42"},
        )

        updated = await node.execute(state)

        assert updated.artifacts["browser_agent_result"]["step_id"] == "my-step-42"

    asyncio.run(scenario())


def test_execute_reports_skipped_and_never_errors_when_input_is_missing() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(session_id="sess-1")  # no search-relevant variables

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["browser_agent_result"]
        assert result["status"] == "skipped"
        assert updated.errors == []  # SKIPPED never contributes to state.errors
        assert updated.current_node == "browser_agent"

    asyncio.run(scenario())


def test_execute_never_raises_for_a_missing_session() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(variables={"search_request": "Acme Corp"})  # no session_id

        updated = await node.execute(state)  # must not raise

        result = updated.artifacts["browser_agent_result"]
        assert result["status"] == "failed"
        assert updated.errors

    asyncio.run(scenario())


def test_execute_preserves_prior_artifacts_and_execution_trace() -> None:
    async def scenario() -> None:
        node = _make_node()
        state = _new_state(
            session_id="sess-1",
            variables={"search_request": "Acme Corp"},
            artifacts={"earlier": "value"},
            execution_trace=["planner", "file_agent", "sql_agent"],
        )

        updated = await node.execute(state)

        assert updated.artifacts["earlier"] == "value"
        assert updated.execution_trace == [
            "planner",
            "file_agent",
            "sql_agent",
            "browser_agent",
        ]

    asyncio.run(scenario())
