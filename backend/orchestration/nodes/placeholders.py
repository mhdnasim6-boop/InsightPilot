"""Placeholder nodes proving the orchestration framework end-to-end.

None of these reason, decide, or do business work — they only update
bookkeeping fields on the state and log their own execution. Real
Planner/Router/business-agent logic arrives in a future phase.
"""

from loguru import logger

from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.utils.time import utc_now


class PlannerNode(OrchestrationNode):
    """Placeholder for the future Planner agent. Does no planning."""

    name = "planner"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)
        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "updated_at": utc_now(),
            }
        )


class RouterNode(OrchestrationNode):
    """Placeholder for future conditional routing. Always advances unconditionally."""

    name = "router"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)
        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "updated_at": utc_now(),
            }
        )


class EndNode(OrchestrationNode):
    """Terminal placeholder node — marks the execution complete."""

    name = "end"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)
        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "status": ExecutionStatus.COMPLETED,
                "updated_at": utc_now(),
            }
        )
