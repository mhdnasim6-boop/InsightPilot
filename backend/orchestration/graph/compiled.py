"""Wraps a compiled LangGraph graph plus the metadata needed to run/inspect/visualize it.

The only object in the application that carries a real LangGraph type
(``CompiledStateGraph``) — never returned by ``OrchestrationService`` to
a caller; only ``GraphMetadata``, Mermaid text, or ``InsightPilotState``
cross that boundary.
"""

from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from backend.orchestration.graph.config import GraphConfig
from backend.orchestration.graph.metadata import GraphMetadata
from backend.orchestration.nodes.base import OrchestrationNode


@dataclass
class CompiledGraph:
    """A compiled orchestration graph, ready to run, inspect, or visualize."""

    compiled: CompiledStateGraph
    nodes: dict[str, OrchestrationNode]
    edges: list[tuple[str, str]]
    entry_point: str | None
    config: GraphConfig
    has_checkpointer: bool = False

    def metadata(self) -> GraphMetadata:
        """Return a LangGraph-independent structural snapshot of this graph."""
        return GraphMetadata.from_graph(self.nodes, self.edges, self.entry_point)
