"""PlannerAgentService: the only entry point external callers use to run PlannerAgent.

Both invocation paths — the direct REST endpoint and ``PlannerAgentNode``
inside the orchestration graph — call this, never ``PlannerAgent`` or
``PlannerAgentResultStore`` directly, mirroring every other agent's own
service.
"""

from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.agents.planner.execution.planner_agent import PlannerAgent
from backend.agents.planner.models.result import PlannerAgentResult
from backend.agents.planner.services.execution_result_store import (
    PlannerAgentResultStore,
)
from backend.planning.models.step import ExecutionStep


class PlannerAgentService:
    """Runs PlannerAgent for one ExecutionStep and makes its result fetchable afterward."""

    def __init__(self, agent: PlannerAgent, result_store: PlannerAgentResultStore) -> None:
        self._agent = agent
        self._result_store = result_store

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> PlannerAgentResult:
        """Run PlannerAgent for ``step`` and store the result under its step_id.

        Raises ``InvalidPlannerAgentInputError`` for malformed input. A
        planning failure is captured in the returned (and stored)
        result's ``status``/``warnings`` instead of raising.
        """
        result = await self._agent.execute(step, session_id)
        self._result_store.put(result)
        return result

    def get_result(self, step_id: str) -> PlannerAgentResult:
        """Fetch a previously stored result. Raises AgentExecutionNotFoundError if unknown."""
        result = self._result_store.get(step_id)
        if result is None:
            raise AgentExecutionNotFoundError(f"No execution result for step '{step_id}'.")
        return result

    def list_results(self) -> list[PlannerAgentResult]:
        """Return every stored result, most recently added first."""
        return self._result_store.list()
