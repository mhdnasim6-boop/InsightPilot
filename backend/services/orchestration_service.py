"""Graph orchestration entry point.

The only object routers (and future callers, including LangGraph-driven
business agents) should use for running orchestration graphs — never
LangGraph, GraphBuilder, or ExecutionEngine directly. LangGraph itself
never leaks past this file: every method here only ever accepts or
returns InsightPilotState, GraphMetadata, or plain Python values.
"""

from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.orchestration.execution.engine import ExecutionEngine
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.graph.compiled import CompiledGraph
from backend.orchestration.graph.metadata import GraphMetadata
from backend.orchestration.state.state import InsightPilotState
from backend.orchestration.visualization.mermaid import generate_mermaid, generate_png


class OrchestrationService:
    """Compiles, runs, streams, and inspects orchestration graphs."""

    def __init__(
        self,
        graph_builder: GraphBuilder,
        execution_engine: ExecutionEngine,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        self._graph_builder = graph_builder
        self._execution_engine = execution_engine
        self._checkpointer = checkpointer
        self._compiled: CompiledGraph | None = None

    def compile_graph(self) -> GraphMetadata:
        """Validate and (re)compile the graph, returning its structural metadata."""
        self._compiled = self._graph_builder.compile(checkpointer=self._checkpointer)
        return self._compiled.metadata()

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        """Run the compiled graph to completion."""
        return await self._execution_engine.run(self._ensure_compiled(), state)

    def stream(self, state: InsightPilotState) -> AsyncIterator[InsightPilotState]:
        """Stream state updates as the graph executes, one per completed node."""
        return self._execution_engine.stream(self._ensure_compiled(), state)

    def validate_state(self, data: dict[str, Any]) -> InsightPilotState:
        """Validate arbitrary data against InsightPilotState, raising on failure."""
        return InsightPilotState.model_validate(data)

    def get_graph_metadata(self) -> GraphMetadata:
        """Describe the compiled graph's nodes, edges, and entry point."""
        return self._ensure_compiled().metadata()

    def get_mermaid(self) -> str:
        """Return a Mermaid flowchart of the compiled graph."""
        return generate_mermaid(self._ensure_compiled())

    def get_png(self) -> bytes | None:
        """Return a PNG rendering of the compiled graph, or None if unavailable."""
        return generate_png(self._ensure_compiled())

    def cancel(self, execution_id: str) -> bool:
        """Cancel a tracked in-flight execution."""
        return self._execution_engine.cancel(execution_id)

    async def resume(self, execution_id: str) -> InsightPilotState:
        """Resume a previously paused (interrupted) execution.

        Raises ``CheckpointNotConfiguredError`` if the graph it ran on
        was compiled without a checkpointer.
        """
        return await self._execution_engine.resume(execution_id)

    async def get_next_nodes(self, execution_id: str) -> tuple[str, ...]:
        """Return the node name(s) that would run next if resumed — empty if complete or unknown."""
        return await self._execution_engine.get_next_nodes(execution_id)

    def inspect(self, execution_id: str) -> InsightPilotState | None:
        """Return the last known state for a tracked execution, or None."""
        return self._execution_engine.inspect(execution_id)

    def _ensure_compiled(self) -> CompiledGraph:
        if self._compiled is None:
            self.compile_graph()
        assert self._compiled is not None  # compile_graph() always sets it; narrows for mypy
        return self._compiled
