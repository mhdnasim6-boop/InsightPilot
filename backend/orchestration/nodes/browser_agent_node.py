"""BrowserAgentNode: the third real orchestration node, mirroring FileAgentNode/SQLAgentNode.

A thin adapter only — reads ``search_request``/``companies``/
``industries``/``products``/``keywords`` out of ``state.variables`` (the
same channel ``FileAgentNode``/``SQLAgentNode`` already read their own
inputs from), delegates to ``BrowserAgentService``, and writes the
structured result back into ``state.artifacts``. Every bit of real
orchestration logic lives in ``backend.agents.browser``; this class
contains none of it.

Unlike File/SQLAgentNode, a SKIPPED result here is expected and common
(every step currently triggers the whole graph, so BrowserAgentNode runs
even for steps with nothing to search for) and never contributes to
``state.errors`` — only a genuine FAILED result does, the same way
File/SQLAgentNode already handle their own failures.
"""

from typing import Any

from loguru import logger

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class BrowserAgentNode(OrchestrationNode):
    """Runs BrowserAgent against whatever step input is already in the graph state."""

    name = "browser_agent"

    def __init__(self, browser_agent_service: BrowserAgentService) -> None:
        self._browser_agent_service = browser_agent_service

    def metadata(self) -> dict[str, Any]:
        """Self-describe for dynamic Planner discovery — never hardcoded elsewhere."""
        return {
            "name": self.name,
            "description": (
                "Gathers external, recent context (market/industry/company/product research) — "
                "never business analysis of the user's own data."
            ),
            "typical_inputs": ["search_request", "companies", "industries", "products", "keywords"],
        }

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)

        step_id = str(state.metadata.get("step_id") or generate_id())
        step = ExecutionStep(
            step_id=step_id, name="Browser Agent Execution", node_name=self.name, inputs=dict(state.variables)
        )

        try:
            result = await self._browser_agent_service.execute_step(step, state.session_id)
        except Exception as exc:  # noqa: BLE001 - malformed step input must not crash the whole graph run
            logger.exception("Node '{}' could not run BrowserAgent for step '{}'", self.name, step_id)
            result = BrowserAgentResult(step_id=step_id, status=ExecutionStatus.FAILED, warnings=[str(exc)])

        errors = state.errors
        if result.status == ExecutionStatus.FAILED:
            errors = [*state.errors, *(result.warnings or [f"BrowserAgent step '{step_id}' failed."])]

        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "artifacts": {**state.artifacts, "browser_agent_result": result.model_dump(mode="json")},
                "errors": errors,
                "updated_at": utc_now(),
            }
        )
