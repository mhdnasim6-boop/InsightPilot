"""ApprovalNode: a named interrupt point immediately before one gated agent node.

Deliberately trivial — like the placeholder nodes in
``nodes/placeholders.py`` — because the actual pause/resume decision
never happens *inside* a node. It happens in ``GraphBuilder.compile()``
(which node names LangGraph's ``interrupt_before`` stops in front of,
always the same five) and in ``PlanExecutor`` (which decides, per the
currently active ``ApprovalPolicy``, whether a given interrupt is
surfaced to a human or transparently resumed). This node's only job is
to exist as a named, addressable point in the graph topology and record
that execution passed it — the same bookkeeping every placeholder node
already does.

Named ``f"approval_{gated_node_name}"`` — ``PlanExecutor`` derives which
agent an interrupt gates by stripping this exact prefix, rather than
maintaining a separate name-mapping table.
"""

from loguru import logger

from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.utils.time import utc_now

APPROVAL_NODE_PREFIX = "approval_"


class ApprovalNode(OrchestrationNode):
    """A named pass-through interrupt point gating one specific agent node."""

    def __init__(self, gated_node_name: str) -> None:
        self.name = f"{APPROVAL_NODE_PREFIX}{gated_node_name}"
        self.gated_node_name = gated_node_name

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        logger.info("Node '{}' executing (execution_id={})", self.name, state.execution_id)
        return state.model_copy(
            update={
                "current_node": self.name,
                "execution_trace": [*state.execution_trace, self.name],
                "updated_at": utc_now(),
            }
        )

    def metadata(self) -> dict[str, object]:
        """Self-describe for introspection, mirroring every real agent node's own override."""
        return {
            "name": self.name,
            "description": f"Interrupt point gating '{self.gated_node_name}' — policy-dependent pause.",
            "gates": self.gated_node_name,
        }
