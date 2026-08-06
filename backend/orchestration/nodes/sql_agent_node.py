"""SQLAgentNode: the second real orchestration node, mirroring FileAgentNode exactly.

A thin adapter only — reads ``connection``/``table_name``/``query``/
``generate_report`` out of ``state.variables`` (the same channel
``FileAgentNode`` reads ``dataset_reference`` from), delegates to
``SQLAgentService``, and writes the structured result back into
``state.artifacts``. Every bit of real orchestration logic lives in
``backend.agents.sql``; this class contains none of it.

Any failure — malformed step input or a pipeline failure deep inside
SQLAgent — is caught here and folded into a FAILED
``AgentExecutionResult`` rather than allowed to crash the graph, for the
exact same reason ``FileAgentNode`` does: a single bad step must never
prevent ``EndNode`` from completing the run.
"""

from typing import Any

from loguru import logger

from backend.agents.file.models.result import AgentExecutionResult
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class SQLAgentNode(OrchestrationNode):
    """Runs SQLAgent against whatever step input is already in the graph state."""

    name = "sql_agent"

    def __init__(self, sql_agent_service: SQLAgentService) -> None:
        self._sql_agent_service = sql_agent_service

    def metadata(self) -> dict[str, Any]:
        """Self-describe for dynamic Planner discovery — never hardcoded elsewhere."""
        return {
            "name": self.name,
            "description": (
                "Imports a table or query from a SQL connection, then cleans, analyzes, and "
                "visualizes it in one pipeline."
            ),
            "typical_inputs": ["connection", "table_name", "query", "generate_report"],
        }

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)

        step_id = str(state.metadata.get("step_id") or generate_id())
        step = ExecutionStep(
            step_id=step_id, name="SQL Agent Execution", node_name=self.name, inputs=dict(state.variables)
        )

        try:
            result = await self._sql_agent_service.execute_step(step, state.session_id)
        except Exception as exc:  # noqa: BLE001 - malformed step input must not crash the whole graph run
            logger.exception("Node '{}' could not run SQLAgent for step '{}'", self.name, step_id)
            result = AgentExecutionResult(step_id=step_id, status=ExecutionStatus.FAILED, warnings=[str(exc)])

        errors = state.errors
        if result.status == ExecutionStatus.FAILED:
            errors = [*state.errors, *(result.warnings or [f"SQLAgent step '{step_id}' failed."])]

        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "artifacts": {**state.artifacts, "sql_agent_result": result.model_dump(mode="json")},
                "errors": errors,
                "updated_at": utc_now(),
            }
        )
