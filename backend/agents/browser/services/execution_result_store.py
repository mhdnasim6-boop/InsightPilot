"""In-memory step_id -> BrowserAgentResult store.

Mirrors ``backend.agents.file.services.execution_result_store`` exactly,
but keyed to ``BrowserAgentResult`` — a genuinely different shape than
``AgentExecutionResult`` (sources/summaries, not dataset/analysis/
report), so it is not shared with File/SQLAgent's store.
"""

from backend.agents.browser.models.result import BrowserAgentResult


class BrowserAgentResultStore:
    """Process-wide store of BrowserAgent results, keyed by step_id."""

    def __init__(self) -> None:
        self._results: dict[str, BrowserAgentResult] = {}

    def put(self, result: BrowserAgentResult) -> None:
        """Store (or overwrite) a result, keyed by its own ``step_id``."""
        self._results[result.step_id] = result

    def get(self, step_id: str) -> BrowserAgentResult | None:
        """Return the result for a step_id, or None if not present."""
        return self._results.get(step_id)

    def list(self) -> list[BrowserAgentResult]:
        """Return every stored result, most recently added first."""
        return list(reversed(self._results.values()))
