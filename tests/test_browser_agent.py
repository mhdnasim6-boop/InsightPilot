"""Agent tests: BrowserAgent orchestrating BrowserService for one ExecutionStep.

Mirrors test_file_agent.py/test_sql_agent.py. BrowserAgent never
searches the web, parses HTML, or writes a summary itself — every
assertion here checks that it correctly sequenced calls into
BrowserService (backed by the real, deterministic MockBrowserProvider),
never that it computed anything itself.
"""

import asyncio

import pytest

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.browser.models.context import SourceResult
from backend.browser.providers.base import BrowserProvider
from backend.browser.providers.mock import MockBrowserProvider
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.services.browser_service import BrowserService
from backend.tools.execution.search_web_tool import SearchWebTool


class _PartiallyFailingProvider(BrowserProvider):
    """Raises for one specific query, deterministic for every other — no network."""

    provider_name = "partially-failing"

    def __init__(self, failing_query: str) -> None:
        self._failing_query = failing_query
        self._delegate = MockBrowserProvider()

    async def search(self, query: str) -> list[SourceResult]:
        if query == self._failing_query:
            raise RuntimeError(f"simulated search failure for '{query}'")
        return await self._delegate.search(query)

    async def summarize(self, query: str, sources: list[SourceResult]) -> str:
        return await self._delegate.summarize(query, sources)


def _make_agent(provider: BrowserProvider | None = None) -> BrowserAgent:
    return BrowserAgent(SearchWebTool(BrowserService(provider or MockBrowserProvider())))


def _step(step_id: str = "s1", **inputs: object) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        name="Browser Agent Run",
        node_name="browser_agent",
        inputs=inputs,
    )


def test_execute_with_a_search_request_runs_a_single_query() -> None:
    async def scenario() -> None:
        agent = _make_agent()

        result = await agent.execute(
            _step(search_request="Acme Corp"), session_id="sess-1"
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.warnings == []
        assert len(result.sources) == 3  # MockBrowserProvider's fixed result count
        assert all(source.query == "Acme Corp" for source in result.sources)
        assert len(result.summaries) == 1
        assert result.summaries[0].query == "Acme Corp"
        assert result.summaries[0].summary
        assert result.execution_time >= 0.0
        assert result.metadata["session_id"] == "sess-1"
        assert result.metadata["queries"] == ["Acme Corp"]

    asyncio.run(scenario())


def test_execute_combines_and_deduplicates_every_query_field() -> None:
    async def scenario() -> None:
        agent = _make_agent()

        result = await agent.execute(
            _step(
                search_request="Acme Corp",
                companies=["Acme Corp", "Globex"],
                industries=["Widgets"],
                products=["Widget Pro"],
                keywords=["market share"],
            ),
            session_id="sess-1",
        )

        assert result.status == ExecutionStatus.COMPLETED
        # "Acme Corp" appears in both search_request and companies - searched once
        assert result.metadata["queries"] == [
            "Acme Corp",
            "Globex",
            "Widgets",
            "Widget Pro",
            "market share",
        ]
        assert len(result.summaries) == 5
        assert len(result.sources) == 5 * 3

    asyncio.run(scenario())


def test_execute_with_no_search_relevant_input_is_gracefully_skipped() -> None:
    async def scenario() -> None:
        agent = _make_agent()

        result = await agent.execute(_step(), session_id="sess-1")

        assert result.status == ExecutionStatus.SKIPPED
        assert result.sources == []
        assert result.summaries == []
        assert result.warnings == []
        assert result.metadata["queries"] == []

    asyncio.run(scenario())


def test_execute_raises_for_missing_session_id() -> None:
    async def scenario() -> None:
        agent = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step(search_request="Acme Corp"), session_id=None)

    asyncio.run(scenario())


def test_execute_raises_for_a_non_string_search_request() -> None:
    async def scenario() -> None:
        agent = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step(search_request=123), session_id="sess-1")

    asyncio.run(scenario())


def test_execute_raises_when_keywords_is_not_a_list_of_strings() -> None:
    async def scenario() -> None:
        agent = _make_agent()

        with pytest.raises(InvalidAgentInputError):
            await agent.execute(_step(keywords="not-a-list"), session_id="sess-1")

    asyncio.run(scenario())


def test_execute_when_one_query_fails_the_others_still_succeed() -> None:
    async def scenario() -> None:
        agent = _make_agent(_PartiallyFailingProvider(failing_query="Globex"))

        result = await agent.execute(
            _step(companies=["Acme Corp", "Globex"]), session_id="sess-1"
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.summaries) == 1
        assert result.summaries[0].query == "Acme Corp"
        assert len(result.warnings) == 1
        assert "Globex" in result.warnings[0]

    asyncio.run(scenario())


def test_execute_when_every_query_fails_returns_a_failed_result() -> None:
    async def scenario() -> None:
        agent = _make_agent(_PartiallyFailingProvider(failing_query="Globex"))

        result = await agent.execute(_step(companies=["Globex"]), session_id="sess-1")

        assert result.status == ExecutionStatus.FAILED
        assert result.sources == []
        assert result.summaries == []
        assert result.warnings

    asyncio.run(scenario())
