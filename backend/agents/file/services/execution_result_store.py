"""In-memory step_id -> AgentExecutionResult store.

Mirrors ``backend.reporting.report_store.ReportStore`` exactly. Needed
because ``FileAgentService.execute_step()`` returns a fresh result to
its caller but "Get execution result" (the REST requirement, and a
FileAgentNode graph run) needs somewhere to fetch it from afterward.
"""

from backend.agents.file.models.result import AgentExecutionResult


class AgentExecutionResultStore:
    """Process-wide store of FileAgent results, keyed by step_id."""

    def __init__(self) -> None:
        self._results: dict[str, AgentExecutionResult] = {}

    def put(self, result: AgentExecutionResult) -> None:
        """Store (or overwrite) a result, keyed by its own ``step_id``."""
        self._results[result.step_id] = result

    def get(self, step_id: str) -> AgentExecutionResult | None:
        """Return the result for a step_id, or None if not present."""
        return self._results.get(step_id)

    def list(self) -> list[AgentExecutionResult]:
        """Return every stored result, most recently added first.

        Defined last in the class body deliberately: a method named
        ``list`` shadows the builtin ``list`` for any annotation that
        follows it in this class (a real ``TypeError`` at import time,
        confirmed empirically while building the MCP registry).
        """
        return list(reversed(self._results.values()))
