"""FileAgentNode: the first real (non-placeholder) orchestration node.

A thin adapter only — reads ``dataset_reference``/``generate_report``
out of ``state.variables`` (exactly how ``PlanExecutor`` already flows
``ExecutionStep.inputs`` into the graph — see
``backend/planning/executor/executor.py``), delegates to
``FileAgentService``, and writes the structured result back into
``state.artifacts``. Every bit of real orchestration logic lives in
``backend.agents.file``; this class contains none of it.

Any failure — malformed step input or a pipeline failure deep inside
FileAgent — is caught here and folded into a FAILED
``AgentExecutionResult`` rather than allowed to crash the graph. That
keeps a single bad step from preventing ``EndNode`` (unmodified, still
runs next) from completing the execution; the business-level outcome is
recorded in ``state.artifacts``/``state.errors`` instead.
"""

from typing import Any

from loguru import logger

from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class FileAgentNode(OrchestrationNode):
    """Runs FileAgent against whatever step input is already in the graph state."""

    name = "file_agent"

    def __init__(self, file_agent_service: FileAgentService) -> None:
        self._file_agent_service = file_agent_service

    def metadata(self) -> dict[str, Any]:
        """Self-describe for dynamic Planner discovery — never hardcoded elsewhere."""
        return {
            "name": self.name,
            "description": "Ingests an uploaded file, then cleans, analyzes, and visualizes it in one pipeline.",
            "typical_inputs": ["dataset_reference", "generate_report"],
        }

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)

        step_id = str(state.metadata.get("step_id") or generate_id())
        step = ExecutionStep(
            step_id=step_id, name="File Agent Execution", node_name=self.name, inputs=dict(state.variables)
        )

        try:
            result = await self._file_agent_service.execute_step(step, state.session_id)
        except Exception as exc:  # noqa: BLE001 - malformed step input must not crash the whole graph run
            logger.exception("Node '{}' could not run FileAgent for step '{}'", self.name, step_id)
            result = AgentExecutionResult(step_id=step_id, status=ExecutionStatus.FAILED, warnings=[str(exc)])

        errors = state.errors
        if result.status == ExecutionStatus.FAILED:
            errors = [*state.errors, *(result.warnings or [f"FileAgent step '{step_id}' failed."])]

        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "artifacts": {**state.artifacts, "file_agent_result": result.model_dump(mode="json")},
                "errors": errors,
                "updated_at": utc_now(),
            }
        )
