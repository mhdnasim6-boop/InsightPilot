"""PlannerAgentNode: replaces the placeholder PlannerNode as the graph's real entry point.

A thin adapter only — reads ``user_request`` straight off
``state.user_request`` (falling back to ``state.variables`` for symmetry
with how every other node reads its own inputs), plus optional planning
hints (``conversation_summary``, ``uploaded_datasets``,
``available_sql_connections``, ``available_browser_context``,
``existing_reports``, ``user_preferences``) out of ``state.variables`` —
delegates to ``PlannerAgentService``, and writes the structured result
back into ``state.artifacts``. Every bit of real planning logic
(including dynamic agent discovery) lives in
``backend.agents.planner.execution.planner_agent``; this class contains
none of it and never executes the plan it stores.

Any failure — malformed step input or a planning failure deep inside
PlannerAgent — is caught here and folded into a FAILED
``PlannerAgentResult`` rather than allowed to crash the graph, the same
way every other node protects ``EndNode`` from a single bad step.
"""

from typing import Any

from loguru import logger

from backend.agents.planner.models.result import PlannerAgentResult
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_INPUT_KEYS = (
    "user_request",
    "conversation_summary",
    "uploaded_datasets",
    "available_sql_connections",
    "available_browser_context",
    "existing_reports",
    "user_preferences",
)


class PlannerAgentNode(OrchestrationNode):
    """Runs PlannerAgent against whatever request context is already in the graph state."""

    name = "planner"

    def __init__(self, planner_agent_service: PlannerAgentService) -> None:
        self._planner_agent_service = planner_agent_service

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)

        step_id = str(state.metadata.get("step_id") or generate_id())
        step = ExecutionStep(
            step_id=step_id, name="Planner Agent Execution", node_name=self.name, inputs=self._collect_inputs(state)
        )

        try:
            result = await self._planner_agent_service.execute_step(step, state.session_id)
        except Exception as exc:  # noqa: BLE001 - malformed step input must not crash the whole graph run
            logger.exception("Node '{}' could not run PlannerAgent for step '{}'", self.name, step_id)
            result = PlannerAgentResult(step_id=step_id, status=ExecutionStatus.FAILED, warnings=[str(exc)])

        errors = state.errors
        if result.status == ExecutionStatus.FAILED:
            errors = [*state.errors, *(result.warnings or [f"PlannerAgent step '{step_id}' failed."])]

        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "artifacts": {**state.artifacts, "planner_agent_result": result.model_dump(mode="json")},
                "errors": errors,
                "updated_at": utc_now(),
            }
        )

    def _collect_inputs(self, state: InsightPilotState) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            key: state.variables[key] for key in _INPUT_KEYS if key in state.variables
        }
        inputs.setdefault("user_request", state.user_request)
        return inputs
