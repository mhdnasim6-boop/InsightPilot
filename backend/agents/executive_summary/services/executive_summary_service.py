"""ExecutiveSummaryService: the only entry point external callers use to run
ExecutiveSummaryAgent.

Both invocation paths — the direct REST endpoint and
``ExecutiveSummaryAgentNode`` inside the orchestration graph — call
this, never ``ExecutiveSummaryAgent`` or ``ExecutiveSummaryResultStore``
directly, mirroring ``ReportAgentService``.

``memory_service`` is an optional collaborator: a successfully produced
summary is remembered as a REPORT memory (tagged ``executive_summary``)
— grouped with report memories per this phase's own "Report Integration:
store reports, executive summaries, recommendations" framing.
``ExecutiveSummaryAgent`` itself is unchanged.
"""

from backend.agents.executive_summary.execution.executive_summary_agent import (
    ExecutiveSummaryAgent,
)
from backend.agents.executive_summary.models.result import ExecutiveSummaryResult
from backend.agents.executive_summary.services.execution_result_store import (
    ExecutiveSummaryResultStore,
)
from backend.agents.file.exceptions.errors import AgentExecutionNotFoundError
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep


class ExecutiveSummaryService:
    """Runs ExecutiveSummaryAgent for one ExecutionStep and makes its result fetchable afterward."""

    def __init__(
        self,
        agent: ExecutiveSummaryAgent,
        result_store: ExecutiveSummaryResultStore,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._agent = agent
        self._result_store = result_store
        self._memory_service = memory_service

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> ExecutiveSummaryResult:
        """Run ExecutiveSummaryAgent for ``step`` and store the result under its step_id.

        Raises ``InvalidAgentInputError`` for malformed input. A bad AI
        call/response is captured in the returned (and stored) result's
        ``status``/``warnings`` instead of raising.
        """
        result = await self._agent.execute(step, session_id)
        self._result_store.put(result)
        self._remember(result, session_id)
        return result

    def _remember(self, result: ExecutiveSummaryResult, session_id: str | None) -> None:
        if self._memory_service is None or result.status != ExecutionStatus.COMPLETED:
            return
        report_id = result.metadata.get("report_id")
        self._memory_service.remember(
            title=f"Executive summary for report {report_id}",
            summary=result.executive_summary[:300],
            memory_type=MemoryType.REPORT,
            scope=MemoryScope.SESSION,
            content={
                "key_findings": result.key_findings,
                "risks": result.risks,
                "recommendations": result.recommendations,
                "confidence": result.confidence,
            },
            importance=result.confidence,
            tags=["executive_summary"],
            references=(
                [MemoryReference(reference_type="report", reference_id=report_id)] if report_id else []
            ),
            metadata={"session_id": session_id},
        )

    def get_result(self, step_id: str) -> ExecutiveSummaryResult:
        """Fetch a previously stored result. Raises AgentExecutionNotFoundError if unknown."""
        result = self._result_store.get(step_id)
        if result is None:
            raise AgentExecutionNotFoundError(f"No execution result for step '{step_id}'.")
        return result

    def list_results(self) -> list[ExecutiveSummaryResult]:
        """Return every stored result, most recently added first."""
        return self._result_store.list()
