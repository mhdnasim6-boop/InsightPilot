"""ReportAgentNode: the fourth real orchestration node.

Unlike File/SQL/BrowserAgentNode — which each read raw input (a dataset
reference, a SQL connection, search topics) straight out of
``state.variables`` — ReportAgentNode reads *already-computed pipeline
outputs* out of ``state.artifacts``, since that is where FileAgentNode/
SQLAgentNode/BrowserAgentNode wrote their own results. This is the
first node with a genuine data dependency on another node's output: it
prefers ``file_agent_result``'s dataset/cleaning/analysis/visualization
if that node completed, falling back to ``sql_agent_result``'s; it reads
``browser_agent_result`` for optional external context. Report
configuration (template/theme/title/subtitle/author) still comes from
``state.variables["report_config"]`` — the original, user-supplied step
input, the same channel every other node's own inputs flow through.

Any failure — malformed step input (most commonly: neither File nor
SQLAgent produced a usable dataset) or a report-building failure deep
inside ReportAgent — is caught here and folded into a FAILED
``ReportAgentResult``, the same way every other node protects
``EndNode`` from a single bad step.
"""

from typing import Any

from loguru import logger

from backend.agents.report.models.result import ReportAgentResult
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_PIPELINE_RESULT_KEYS = ("file_agent_result", "sql_agent_result")


class ReportAgentNode(OrchestrationNode):
    """Runs ReportAgent against whichever prior agent's pipeline output is in the graph state."""

    name = "report_agent"

    def __init__(self, report_agent_service: ReportAgentService) -> None:
        self._report_agent_service = report_agent_service

    def metadata(self) -> dict[str, Any]:
        """Self-describe for dynamic Planner discovery — never hardcoded elsewhere."""
        return {
            "name": self.name,
            "description": (
                "Builds a formal report document from a prior FileAgent/SQLAgent result (and "
                "optional BrowserAgent context) — depends on one of those already having run."
            ),
            "typical_inputs": ["report_config"],
        }

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)

        step_id = str(state.metadata.get("step_id") or generate_id())
        step = ExecutionStep(
            step_id=step_id, name="Report Agent Execution", node_name=self.name, inputs=self._collect_inputs(state)
        )

        try:
            result = await self._report_agent_service.execute_step(step, state.session_id)
        except Exception as exc:  # noqa: BLE001 - malformed step input must not crash the whole graph run
            logger.exception("Node '{}' could not run ReportAgent for step '{}'", self.name, step_id)
            result = ReportAgentResult(step_id=step_id, status=ExecutionStatus.FAILED, warnings=[str(exc)])

        errors = state.errors
        if result.status == ExecutionStatus.FAILED:
            errors = [*state.errors, *(result.warnings or [f"ReportAgent step '{step_id}' failed."])]

        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "artifacts": {**state.artifacts, "report_agent_result": result.model_dump(mode="json")},
                "errors": errors,
                "updated_at": utc_now(),
            }
        )

    def _collect_inputs(self, state: InsightPilotState) -> dict[str, Any]:
        inputs: dict[str, Any] = {}

        pipeline_result = self._select_pipeline_result(state)
        if pipeline_result is not None:
            for artifact_key, input_key in (
                ("dataset", "dataset"),
                ("cleaning", "cleaning_outcome"),
                ("analysis", "analysis_result"),
                ("visualization", "visualization_result"),
            ):
                value = pipeline_result.get(artifact_key)
                if value is not None:
                    inputs[input_key] = value

        browser_result = state.artifacts.get("browser_agent_result")
        if isinstance(browser_result, dict) and browser_result.get("status") == "completed":
            inputs["browser_agent_result"] = browser_result

        report_config = state.variables.get("report_config")
        if isinstance(report_config, dict):
            inputs["report_config"] = report_config

        return inputs

    def _select_pipeline_result(self, state: InsightPilotState) -> dict[str, Any] | None:
        """Prefer FileAgent's own completed result; fall back to SQLAgent's."""
        for key in _PIPELINE_RESULT_KEYS:
            candidate = state.artifacts.get(key)
            if isinstance(candidate, dict) and candidate.get("status") == "completed" and candidate.get("dataset"):
                return candidate
        return None
