"""SQLAgentService: the only entry point external callers use to run SQLAgent.

Both invocation paths — the direct REST endpoint and ``SQLAgentNode``
inside the orchestration graph — call this, never ``SQLAgent`` or
``AgentExecutionResultStore`` directly.

No ``backend/agents/sql/models/`` or ``backend/agents/sql/exceptions/``
package exists: ``AgentExecutionResult``, ``AgentExecutionResultStore``,
``InvalidAgentInputError``, and ``AgentExecutionNotFoundError`` are
reused directly from ``backend.agents.file`` — none of them are
FileAgent-specific in shape (the class/exception names were already
agent-agnostic), and the DI layer binds SQLAgentService to the *same*
``AgentExecutionResultStore`` instance FileAgentService uses, so one
execution result is fetchable the same way regardless of which agent
produced it. Redefining equivalents here would be exactly the kind of
duplicated logic this phase's "no new business logic" scope forbids.
"""

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.file.services.remember_agent_execution_result import (
    remember_agent_execution_result,
)
from backend.agents.sql.execution.sql_agent import SQLAgent
from backend.memory.services.memory_service import MemoryService
from backend.planning.models.step import ExecutionStep


class SQLAgentService:
    """Runs SQLAgent for one ExecutionStep and makes its result fetchable afterward."""

    def __init__(
        self,
        agent: SQLAgent,
        result_store: AgentExecutionResultStore,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._agent = agent
        self._result_store = result_store
        self._memory_service = memory_service

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> AgentExecutionResult:
        """Run SQLAgent for ``step`` and store the result under its step_id.

        Raises ``InvalidAgentInputError`` for malformed input; a
        pipeline failure is captured in the returned (and stored)
        result's ``status``/``warnings`` instead of raising.
        """
        result = await self._agent.execute(step, session_id)
        self._result_store.put(result)
        remember_agent_execution_result(self._memory_service, result, "sql_agent", session_id)
        return result

    def get_result(self, step_id: str) -> AgentExecutionResult:
        """Fetch a previously stored result. Raises AgentExecutionNotFoundError if unknown."""
        result = self._result_store.get(step_id)
        if result is None:
            raise AgentExecutionNotFoundError(f"No execution result for step '{step_id}'.")
        return result

    def list_results(self) -> list[AgentExecutionResult]:
        """Return every stored result, most recently added first."""
        return self._result_store.list()
