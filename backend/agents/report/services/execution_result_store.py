"""In-memory step_id -> ReportAgentResult store.

Mirrors ``backend.agents.browser.services.execution_result_store``
exactly, but keyed to ``ReportAgentResult`` — kept independent from
File/SQL's shared store and from Browser's own store, since none of
those shapes match.
"""

from backend.agents.report.models.result import ReportAgentResult


class ReportAgentResultStore:
    """Process-wide store of ReportAgent results, keyed by step_id."""

    def __init__(self) -> None:
        self._results: dict[str, ReportAgentResult] = {}

    def put(self, result: ReportAgentResult) -> None:
        """Store (or overwrite) a result, keyed by its own ``step_id``."""
        self._results[result.step_id] = result

    def get(self, step_id: str) -> ReportAgentResult | None:
        """Return the result for a step_id, or None if not present."""
        return self._results.get(step_id)

    def list(self) -> list[ReportAgentResult]:
        """Return every stored result, most recently added first."""
        return list(reversed(self._results.values()))
