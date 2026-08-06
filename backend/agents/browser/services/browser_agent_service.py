"""BrowserAgentService: the only entry point external callers use to run BrowserAgent.

Both invocation paths — the direct REST endpoint and ``BrowserAgentNode``
inside the orchestration graph — call this, never ``BrowserAgent`` or
``BrowserAgentResultStore`` directly, mirroring ``FileAgentService``.

``memory_service`` is an optional collaborator: when present, every
``SearchOutcome`` the step produced is remembered as an
EXTERNAL_KNOWLEDGE memory — external context found for a query, never
analyzed data. ``BrowserAgent`` itself is unchanged.
"""

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.browser.services.execution_result_store import (
    BrowserAgentResultStore,
)
from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.planning.models.step import ExecutionStep


class BrowserAgentService:
    """Runs BrowserAgent for one ExecutionStep and makes its result fetchable afterward."""

    def __init__(
        self,
        agent: BrowserAgent,
        result_store: BrowserAgentResultStore,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._agent = agent
        self._result_store = result_store
        self._memory_service = memory_service

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> BrowserAgentResult:
        """Run BrowserAgent for ``step`` and store the result under its step_id.

        Raises ``InvalidAgentInputError`` for malformed input. A step
        with nothing to search for is a SKIPPED result, not a raise; a
        search failure is a FAILED result, not a raise either.
        """
        result = await self._agent.execute(step, session_id)
        self._result_store.put(result)
        self._remember(result, session_id)
        return result

    def _remember(self, result: BrowserAgentResult, session_id: str | None) -> None:
        if self._memory_service is None:
            return
        for outcome in result.summaries:
            self._memory_service.remember(
                title=f"Web research: {outcome.query}",
                summary=outcome.summary,
                memory_type=MemoryType.EXTERNAL_KNOWLEDGE,
                scope=MemoryScope.SESSION,
                content={"query": outcome.query, "sources": [source.url for source in outcome.sources]},
                tags=["browser_agent"],
                metadata={"session_id": session_id},
            )

    def get_result(self, step_id: str) -> BrowserAgentResult:
        """Fetch a previously stored result. Raises AgentExecutionNotFoundError if unknown."""
        result = self._result_store.get(step_id)
        if result is None:
            raise AgentExecutionNotFoundError(f"No execution result for step '{step_id}'.")
        return result

    def list_results(self) -> list[BrowserAgentResult]:
        """Return every stored result, most recently added first."""
        return self._result_store.list()
