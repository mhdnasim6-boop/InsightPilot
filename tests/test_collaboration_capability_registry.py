"""Tests for AgentCapabilityRegistry: dynamic discovery from GraphBuilder,
excluding Planner/Router/End and approval interrupt nodes.
"""

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.approval_node import ApprovalNode
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState


class _StubAgentNode(OrchestrationNode):
    def __init__(self, name: str, description: str = "", typical_inputs: list[str] | None = None) -> None:
        self.name = name
        self._description = description
        self._typical_inputs = typical_inputs or []

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state

    def metadata(self) -> dict[str, object]:
        return {"name": self.name, "description": self._description, "typical_inputs": self._typical_inputs}


def _builder_with(*nodes: OrchestrationNode) -> GraphBuilder:
    builder = GraphBuilder()
    for node in nodes:
        builder.add_node(node)
    builder.set_entry_point(nodes[0].name)
    return builder


def test_discover_returns_one_capability_per_registered_agent() -> None:
    builder = _builder_with(
        _StubAgentNode("file_agent", "Ingests files.", ["dataset_reference"]),
        _StubAgentNode("sql_agent", "Queries SQL."),
    )

    capabilities = AgentCapabilityRegistry(builder).discover()

    assert {c.name for c in capabilities} == {"file_agent", "sql_agent"}
    file_capability = next(c for c in capabilities if c.name == "file_agent")
    assert file_capability.description == "Ingests files."
    assert file_capability.accepted_inputs == ["dataset_reference"]
    assert file_capability.produced_outputs  # populated from the static table
    assert file_capability.estimated_duration > 0


def test_discover_excludes_planner_router_end() -> None:
    builder = _builder_with(
        _StubAgentNode("planner"), _StubAgentNode("router"), _StubAgentNode("end"), _StubAgentNode("file_agent")
    )

    capabilities = AgentCapabilityRegistry(builder).discover()

    assert {c.name for c in capabilities} == {"file_agent"}


def test_discover_excludes_approval_interrupt_nodes() -> None:
    builder = _builder_with(_StubAgentNode("sql_agent"), ApprovalNode("sql_agent"))

    capabilities = AgentCapabilityRegistry(builder).discover()

    assert {c.name for c in capabilities} == {"sql_agent"}


def test_get_returns_none_for_unregistered_agent() -> None:
    builder = _builder_with(_StubAgentNode("file_agent"))
    assert AgentCapabilityRegistry(builder).get("nonexistent_agent") is None


def test_get_returns_the_matching_capability() -> None:
    builder = _builder_with(_StubAgentNode("browser_agent", "Gathers external context."))
    capability = AgentCapabilityRegistry(builder).get("browser_agent")
    assert capability is not None
    assert capability.description == "Gathers external context."


def test_agent_without_static_capability_data_still_discoverable() -> None:
    builder = _builder_with(_StubAgentNode("some_future_agent", "New agent."))
    capabilities = AgentCapabilityRegistry(builder).discover()
    capability = capabilities[0]
    assert capability.name == "some_future_agent"
    assert capability.produced_outputs == []
    assert capability.estimated_cost == 0.0
