"""Common interface every orchestration node must implement.

Placeholder nodes today (``PlannerNode``, ``RouterNode``, ``EndNode``);
real business agents later inherit this same interface — ``GraphBuilder``
and ``ExecutionEngine`` only ever depend on this contract, never on a
concrete node type.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.orchestration.state.state import InsightPilotState


class OrchestrationNode(ABC):
    """Contract every graph node (placeholder or future agent) must satisfy."""

    name: str

    @abstractmethod
    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        """Run this node's logic against the current state and return the updated state."""

    def validate(self, state: InsightPilotState) -> bool:
        """Return whether this node can run against the given state. Default: always valid."""
        return True

    def metadata(self) -> dict[str, Any]:
        """Describe this node for introspection/visualization. Default: just its name."""
        return {"name": self.name}
