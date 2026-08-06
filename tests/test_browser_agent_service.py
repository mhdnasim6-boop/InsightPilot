"""Tests for BrowserAgentService: execute_step stores results; get_result/list_results
fetch them. Mirrors test_file_agent_service.py/test_sql_agent_service.py.
"""

import asyncio

import pytest

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.browser.services.execution_result_store import (
    BrowserAgentResultStore,
)
from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.browser.providers.mock import MockBrowserProvider
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.services.browser_service import BrowserService
from backend.tools.execution.search_web_tool import SearchWebTool


def _make_service() -> BrowserAgentService:
    agent = BrowserAgent(SearchWebTool(BrowserService(MockBrowserProvider())))
    return BrowserAgentService(agent, BrowserAgentResultStore())


def _step(step_id: str) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        name="Run",
        node_name="browser_agent",
        inputs={"search_request": "Acme Corp"},
    )


def test_execute_step_stores_and_returns_the_same_result() -> None:
    async def scenario() -> None:
        service = _make_service()

        result = await service.execute_step(_step("s1"), session_id="sess-1")

        assert result.status == ExecutionStatus.COMPLETED
        assert service.get_result("s1") == result

    asyncio.run(scenario())


def test_get_result_raises_for_an_unknown_step_id() -> None:
    service = _make_service()
    with pytest.raises(AgentExecutionNotFoundError):
        service.get_result("never-ran")


def test_list_results_returns_most_recent_first() -> None:
    async def scenario() -> None:
        service = _make_service()

        first = await service.execute_step(_step("s1"), session_id="sess-1")
        second = await service.execute_step(_step("s2"), session_id="sess-1")

        listed = service.list_results()
        assert listed[0].step_id == second.step_id
        assert listed[1].step_id == first.step_id

    asyncio.run(scenario())


def test_execute_step_overwrites_a_result_for_a_repeated_step_id() -> None:
    async def scenario() -> None:
        service = _make_service()

        await service.execute_step(_step("s1"), session_id="sess-1")
        await service.execute_step(_step("s1"), session_id="sess-2")

        assert service.get_result("s1").metadata["session_id"] == "sess-2"
        assert len(service.list_results()) == 1

    asyncio.run(scenario())
