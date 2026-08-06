"""BrowserAgent: orchestrates SearchWebTool for one ExecutionStep.

One ``SearchWebTool.execute()`` call per distinct query (Tool Layer,
Phase 22) — never a network call, an HTML parse, or a summarization
prompt of its own; all of that lives behind ``BrowserService``, which
``SearchWebTool`` wraps. No business logic: no KPI, no chart, no
touching an ``AnalysisResult``. A step with no search-relevant input
(see ``validate_agent_input``) is a graceful SKIPPED result, not a
failure. One query failing does not discard the others' results — the
overall result is FAILED only if every query failed.
"""

import time

from loguru import logger

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.browser.validation.input_validator import validate_agent_input
from backend.browser.models.context import SourceResult
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.tools.execution.search_web_tool import SearchWebTool
from backend.tools.models.inputs import SearchWebInput


class BrowserAgent:
    """Runs SearchWebTool for every search query a step asks for, and nothing else."""

    def __init__(self, search_web_tool: SearchWebTool) -> None:
        self._search_web_tool = search_web_tool

    async def execute(self, step: ExecutionStep, session_id: str | None) -> BrowserAgentResult:
        """Search for every query in ``step.inputs`` and return the combined result.

        Raises ``InvalidAgentInputError`` for malformed input (missing
        session, or a present field with the wrong shape). A step with
        no search-relevant input at all returns a SKIPPED result instead
        of raising — see the module docstring.
        """
        queries = validate_agent_input(step, session_id)
        start = time.perf_counter()

        if not queries:
            return BrowserAgentResult(
                step_id=step.step_id,
                status=ExecutionStatus.SKIPPED,
                execution_time=time.perf_counter() - start,
                metadata={"session_id": session_id, "queries": [], "reason": "no search-relevant input present"},
            )

        warnings: list[str] = []
        sources: list[SourceResult] = []
        summaries = []

        for query in queries:
            try:
                outcome = await self._search_web_tool.execute(SearchWebInput(query=query))
            except Exception as exc:  # noqa: BLE001 - one query's failure must not discard the others
                logger.exception("BrowserAgent step '{}' failed to search for '{}'", step.step_id, query)
                warnings.append(f"Search for '{query}' failed: {exc}")
                continue
            sources.extend(outcome.sources)
            summaries.append(outcome)

        status = ExecutionStatus.COMPLETED if summaries else ExecutionStatus.FAILED
        execution_time = time.perf_counter() - start
        return BrowserAgentResult(
            step_id=step.step_id,
            status=status,
            sources=sources,
            summaries=summaries,
            warnings=warnings,
            execution_time=execution_time,
            metadata={"session_id": session_id, "queries": queries},
        )
