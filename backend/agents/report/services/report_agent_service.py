"""ReportAgentService: the only entry point external callers use to run ReportAgent.

Both invocation paths — the direct REST endpoint and ``ReportAgentNode``
inside the orchestration graph — call this, never ``ReportAgent`` or
``ReportAgentResultStore`` directly, mirroring ``BrowserAgentService``.
"""

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.agents.report.execution.report_agent import ReportAgent
from backend.agents.report.models.result import ReportAgentResult
from backend.agents.report.services.execution_result_store import (
    ReportAgentResultStore,
)
from backend.planning.models.step import ExecutionStep


class ReportAgentService:
    """Runs ReportAgent for one ExecutionStep and makes its result fetchable afterward."""

    def __init__(self, agent: ReportAgent, result_store: ReportAgentResultStore) -> None:
        self._agent = agent
        self._result_store = result_store

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> ReportAgentResult:
        """Run ReportAgent for ``step`` and store the result under its step_id.

        Raises ``InvalidAgentInputError`` for malformed input. A
        report-building failure is captured in the returned (and
        stored) result's ``status``/``warnings`` instead of raising.
        """
        result = await self._agent.execute(step, session_id)
        self._result_store.put(result)
        return result

    def get_result(self, step_id: str) -> ReportAgentResult:
        """Fetch a previously stored result. Raises AgentExecutionNotFoundError if unknown."""
        result = self._result_store.get(step_id)
        if result is None:
            raise AgentExecutionNotFoundError(f"No execution result for step '{step_id}'.")
        return result

    def list_results(self) -> list[ReportAgentResult]:
        """Return every stored result, most recently added first."""
        return self._result_store.list()
