"""AgentCapabilityRegistry: dynamic agent discovery for the collaboration layer.

``name``/``description``/``accepted_inputs`` are read fresh from the live
``GraphBuilder`` on every call (never hardcoded) — the exact same source
``PlannerAgent._discover_agents()`` used before this phase (see
``OrchestrationNode.metadata()``'s own ``typical_inputs``). Only
``produced_outputs``/``supported_tools``/``estimated_cost``/
``estimated_duration`` are genuinely new metadata with no existing
source in the codebase, so they're layered on via a small static table
here — the one place this phase's own new capability data lives.
"""

from dataclasses import dataclass, field

from backend.collaboration.models.agent_capability import AgentCapability
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.approval_node import APPROVAL_NODE_PREFIX

_NON_AGENT_NODE_NAMES = frozenset({"planner", "router", "end"})


@dataclass(frozen=True)
class _StaticCapabilityData:
    """The capability fields with no existing source in the codebase — new to this phase."""

    produced_outputs: list[str] = field(default_factory=list)
    supported_tools: list[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_duration: float = 0.0


_STATIC_CAPABILITY_DATA: dict[str, _StaticCapabilityData] = {
    "planner": _StaticCapabilityData(produced_outputs=["execution_plan"], estimated_cost=0.01, estimated_duration=3.0),
    "file_agent": _StaticCapabilityData(
        produced_outputs=["dataset", "cleaning", "analysis", "visualization", "report"],
        supported_tools=["ingest_dataset", "clean_dataset", "analyze_dataset", "generate_visualization", "generate_report"],
        estimated_cost=0.02,
        estimated_duration=6.0,
    ),
    "sql_agent": _StaticCapabilityData(
        produced_outputs=["dataset", "cleaning", "analysis", "visualization", "report"],
        supported_tools=["query_database", "clean_dataset", "analyze_dataset", "generate_visualization", "generate_report"],
        estimated_cost=0.02,
        estimated_duration=6.0,
    ),
    "browser_agent": _StaticCapabilityData(
        produced_outputs=["sources", "summaries"], supported_tools=["search_web"], estimated_cost=0.01, estimated_duration=4.0
    ),
    "report_agent": _StaticCapabilityData(
        produced_outputs=["report_document"], supported_tools=["generate_report"], estimated_cost=0.03, estimated_duration=5.0
    ),
    "executive_summary_agent": _StaticCapabilityData(
        produced_outputs=["executive_summary", "key_findings", "risks", "recommendations"],
        supported_tools=["generate_executive_summary"],
        estimated_cost=0.05,
        estimated_duration=4.0,
    ),
}


class AgentCapabilityRegistry:
    """Discovers every registered agent's capability, live, from GraphBuilder."""

    def __init__(self, graph_builder: GraphBuilder) -> None:
        self._graph_builder = graph_builder

    def discover(self) -> list[AgentCapability]:
        """Return one AgentCapability per registered agent node (Planner/Router/End excluded)."""
        graph_metadata = self._graph_builder.export()
        capabilities = []
        for node in graph_metadata.nodes:
            if node.name in _NON_AGENT_NODE_NAMES or node.name.startswith(APPROVAL_NODE_PREFIX):
                continue
            extra = _STATIC_CAPABILITY_DATA.get(node.name, _StaticCapabilityData())
            capabilities.append(
                AgentCapability(
                    name=node.name,
                    description=str(node.details.get("description", "")),
                    accepted_inputs=list(node.details.get("typical_inputs", [])),
                    produced_outputs=extra.produced_outputs,
                    supported_tools=extra.supported_tools,
                    estimated_cost=extra.estimated_cost,
                    estimated_duration=extra.estimated_duration,
                )
            )
        return capabilities

    def get(self, name: str) -> AgentCapability | None:
        """Return one agent's capability by name, or None if unregistered."""
        return next((capability for capability in self.discover() if capability.name == name), None)
