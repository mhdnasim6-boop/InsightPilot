"""LangGraph-independent description of a graph's structure."""

from typing import Any

from pydantic import BaseModel, Field

from backend.orchestration.nodes.base import OrchestrationNode


class NodeMetadata(BaseModel):
    """Descriptive metadata about a single registered node."""

    name: str
    details: dict[str, Any] = Field(default_factory=dict)


class EdgeMetadata(BaseModel):
    """A directed edge between two node names (or START/END)."""

    source: str
    target: str


class GraphMetadata(BaseModel):
    """A structural snapshot of a graph: its nodes, edges, and entry point."""

    nodes: list[NodeMetadata] = Field(default_factory=list)
    edges: list[EdgeMetadata] = Field(default_factory=list)
    entry_point: str | None = None

    @classmethod
    def from_graph(
        cls,
        nodes: dict[str, OrchestrationNode],
        edges: list[tuple[str, str]],
        entry_point: str | None,
    ) -> "GraphMetadata":
        """Build a snapshot from a builder's or compiled graph's raw node/edge data."""
        return cls(
            nodes=[NodeMetadata(name=node.name, details=node.metadata()) for node in nodes.values()],
            edges=[EdgeMetadata(source=source, target=target) for source, target in edges],
            entry_point=entry_point,
        )
