"""In-memory step_id -> PlannerAgentResult store.

Mirrors ``backend.agents.report.services.execution_result_store`` exactly,
but keyed to ``PlannerAgentResult`` — kept independent from every other
agent's own store, since none of those shapes match.
"""

from backend.agents.planner.models.result import PlannerAgentResult


class PlannerAgentResultStore:
    """Process-wide store of PlannerAgent results, keyed by step_id."""

    def __init__(self) -> None:
        self._results: dict[str, PlannerAgentResult] = {}

    def put(self, result: PlannerAgentResult) -> None:
        """Store (or overwrite) a result, keyed by its own ``step_id``."""
        self._results[result.step_id] = result

    def get(self, step_id: str) -> PlannerAgentResult | None:
        """Return the result for a step_id, or None if not present."""
        return self._results.get(step_id)

    def list(self) -> list[PlannerAgentResult]:
        """Return every stored result, most recently added first."""
        return list(reversed(self._results.values()))
