"""In-memory step_id -> ExecutiveSummaryResult store.

Mirrors ``backend.agents.report.services.execution_result_store``
exactly, but keyed to ``ExecutiveSummaryResult`` — kept independent from
every other agent's store, per this phase's explicit requirement.
"""

from backend.agents.executive_summary.models.result import ExecutiveSummaryResult


class ExecutiveSummaryResultStore:
    """Process-wide store of ExecutiveSummaryAgent results, keyed by step_id."""

    def __init__(self) -> None:
        self._results: dict[str, ExecutiveSummaryResult] = {}

    def put(self, result: ExecutiveSummaryResult) -> None:
        """Store (or overwrite) a result, keyed by its own ``step_id``."""
        self._results[result.step_id] = result

    def get(self, step_id: str) -> ExecutiveSummaryResult | None:
        """Return the result for a step_id, or None if not present."""
        return self._results.get(step_id)

    def list(self) -> list[ExecutiveSummaryResult]:
        """Return every stored result, most recently added first."""
        return list(reversed(self._results.values()))
