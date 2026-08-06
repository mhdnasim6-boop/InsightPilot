"""ExecutiveSummaryAgentNode: the fifth real orchestration node.

Like ReportAgentNode, this node has no raw input of its own to read from
``state.variables`` — it reads whatever earlier nodes already wrote to
``state.artifacts``: ``report_agent_result``'s own ``report_document``
(its one required input), ``browser_agent_result`` for optional external
context, and small ``dataset_metadata``/``analysis_metadata`` facts
pulled from whichever of ``file_agent_result``/``sql_agent_result``
completed (the same source ReportAgentNode itself preferred, so both
nodes agree on which pipeline result was "the" one for this run).

Any failure — malformed step input (most commonly: ReportAgent didn't
produce a usable ``report_document``) or the AI call/response failing
deep inside ExecutiveSummaryAgent — is caught here and folded into a
FAILED ``ExecutiveSummaryResult``, the same way every other node
protects ``EndNode`` from a single bad step.
"""

from typing import Any

from loguru import logger

from backend.agents.executive_summary.models.result import ExecutiveSummaryResult
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_PIPELINE_RESULT_KEYS = ("file_agent_result", "sql_agent_result")


class ExecutiveSummaryAgentNode(OrchestrationNode):
    """Runs ExecutiveSummaryAgent against whatever ReportAgent (and friends) already produced."""

    name = "executive_summary_agent"

    def __init__(self, executive_summary_service: ExecutiveSummaryService) -> None:
        self._executive_summary_service = executive_summary_service

    def metadata(self) -> dict[str, Any]:
        """Self-describe for dynamic Planner discovery — never hardcoded elsewhere."""
        return {
            "name": self.name,
            "description": (
                "Writes a grounded executive summary and business recommendations from an "
                "already-built report — depends on ReportAgent already having run."
            ),
            "typical_inputs": [],
        }

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)

        step_id = str(state.metadata.get("step_id") or generate_id())
        step = ExecutionStep(
            step_id=step_id,
            name="Executive Summary Agent Execution",
            node_name=self.name,
            inputs=self._collect_inputs(state),
        )

        try:
            result = await self._executive_summary_service.execute_step(step, state.session_id)
        except Exception as exc:  # noqa: BLE001 - malformed step input must not crash the whole graph run
            logger.exception("Node '{}' could not run ExecutiveSummaryAgent for step '{}'", self.name, step_id)
            result = ExecutiveSummaryResult(step_id=step_id, status=ExecutionStatus.FAILED, warnings=[str(exc)])

        errors = state.errors
        if result.status == ExecutionStatus.FAILED:
            errors = [*state.errors, *(result.warnings or [f"ExecutiveSummaryAgent step '{step_id}' failed."])]

        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "artifacts": {**state.artifacts, "executive_summary_result": result.model_dump(mode="json")},
                "errors": errors,
                "updated_at": utc_now(),
            }
        )

    def _collect_inputs(self, state: InsightPilotState) -> dict[str, Any]:
        inputs: dict[str, Any] = {}

        report_agent_result = state.artifacts.get("report_agent_result")
        if isinstance(report_agent_result, dict) and report_agent_result.get("status") == "completed":
            report_document = report_agent_result.get("report_document")
            if report_document is not None:
                inputs["report_document"] = report_document

        browser_result = state.artifacts.get("browser_agent_result")
        if isinstance(browser_result, dict) and browser_result.get("status") == "completed":
            inputs["browser_agent_result"] = browser_result

        pipeline_result = self._select_pipeline_result(state)
        if pipeline_result is not None:
            dataset = pipeline_result.get("dataset") or {}
            inputs["dataset_metadata"] = {
                "dataset_id": dataset.get("dataset_id"),
                "dataset_name": dataset.get("dataset_name"),
                "row_count": dataset.get("row_count"),
                "column_count": dataset.get("column_count"),
            }
            analysis = pipeline_result.get("analysis")
            if analysis is not None:
                inputs["analysis_metadata"] = {
                    "kpi_count": len(analysis.get("kpis", [])),
                    "insight_count": len(analysis.get("insights", [])),
                }

        return inputs

    def _select_pipeline_result(self, state: InsightPilotState) -> dict[str, Any] | None:
        """Prefer FileAgent's own completed result; fall back to SQLAgent's — the same
        preference ReportAgentNode itself uses, so both nodes agree on "the" pipeline result."""
        for key in _PIPELINE_RESULT_KEYS:
            candidate = state.artifacts.get(key)
            if isinstance(candidate, dict) and candidate.get("status") == "completed" and candidate.get("dataset"):
                return candidate
        return None
