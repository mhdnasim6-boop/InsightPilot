"""FileAgentService: the only entry point external callers use to run FileAgent.

Both invocation paths — the direct REST endpoint and ``FileAgentNode``
inside the orchestration graph — call this, never ``FileAgent`` or
``AgentExecutionResultStore`` directly, so a result from either path is
retrievable the same way afterward.

``memory_service`` is an optional collaborator: when present, whatever
DATASET/ANALYSIS/VISUALIZATION artifacts a step produced are remembered
via the shared ``remember_agent_execution_result()`` helper (also used
by ``SQLAgentService``, since both produce the identical result shape).
``FileAgent`` itself is unchanged — only this service calls
``MemoryService``.
"""

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.agents.file.execution.file_agent import FileAgent
from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.file.services.remember_agent_execution_result import (
    remember_agent_execution_result,
)
from backend.memory.services.memory_service import MemoryService
from backend.planning.models.step import ExecutionStep


class FileAgentService:
    """Runs FileAgent for one ExecutionStep and makes its result fetchable afterward."""

    def __init__(
        self,
        agent: FileAgent,
        result_store: AgentExecutionResultStore,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._agent = agent
        self._result_store = result_store
        self._memory_service = memory_service

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> AgentExecutionResult:
        """Run FileAgent for ``step`` and store the result under its step_id.

        Raises ``InvalidAgentInputError`` for malformed input; a
        pipeline failure is captured in the returned (and stored)
        result's ``status``/``warnings`` instead of raising.
        """
        result = await self._agent.execute(step, session_id)
        self._result_store.put(result)
        remember_agent_execution_result(self._memory_service, result, "file_agent", session_id)
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
