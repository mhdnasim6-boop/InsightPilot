"""Reusable builder for LangGraph-backed orchestration graphs.

This file (and ``default_graph.py``, ``compiled.py``) are the only
places in the entire application that import ``langgraph`` directly.
Everything above this layer — ``OrchestrationService``, routers, future
callers — works exclusively with ``InsightPilotState``, ``GraphMetadata``,
and ``CompiledGraph``.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from backend.observability.context import agent_context
from backend.orchestration.events.bus import EventBus
from backend.orchestration.events.events import NodeCompleted, NodeStarted
from backend.orchestration.exceptions import GraphValidationError
from backend.orchestration.graph.compiled import CompiledGraph
from backend.orchestration.graph.config import GraphConfig
from backend.orchestration.graph.metadata import GraphMetadata
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.utils.time import utc_now


class GraphBuilder:
    """Registers nodes/edges and compiles them into a runnable orchestration graph."""

    def __init__(self, config: GraphConfig | None = None, event_bus: EventBus | None = None) -> None:
        self._config = config or GraphConfig()
        self._event_bus = event_bus or EventBus()
        self._graph = StateGraph(InsightPilotState)
        self._nodes: dict[str, OrchestrationNode] = {}
        self._edges: list[tuple[str, str]] = []
        self._entry_point: str | None = None

    def add_node(self, node: OrchestrationNode) -> "GraphBuilder":
        """Register a node. Execution is wrapped so NodeStarted/NodeCompleted fire automatically."""
        retry_policy = (
            RetryPolicy(max_attempts=self._config.retry_max_attempts)
            if self._config.retry_max_attempts > 1
            else None
        )
        # LangGraph's add_node() overloads are resolved against its own NodeInputT
        # bound (TypedDict/dataclass/BaseModel-like input types); mypy can't match
        # our plain async Callable against that overload set, even though this
        # exact call shape (name, async fn, timeout=, retry_policy=) is the
        # library's own documented usage and was empirically verified to run
        # correctly against the installed LangGraph version.
        self._graph.add_node(  # type: ignore[call-overload]
            node.name,
            self._wrap(node),
            timeout=self._config.timeout_seconds,
            retry_policy=retry_policy,
        )
        self._nodes[node.name] = node
        return self

    def add_edge(self, source: str, target: str) -> "GraphBuilder":
        """Register a direct edge between two registered nodes (or START/END)."""
        self._graph.add_edge(source, target)
        self._edges.append((source, target))
        return self

    def set_entry_point(self, node_name: str) -> "GraphBuilder":
        """Mark a registered node as the graph's entry point (edge from START)."""
        self._graph.add_edge(START, node_name)
        self._entry_point = node_name
        return self

    def validate(self) -> None:
        """Ensure the graph is well-formed. Raises GraphValidationError otherwise."""
        if self._entry_point is None:
            raise GraphValidationError("Graph has no entry point; call set_entry_point() before compiling.")
        for source, target in self._edges:
            if source not in self._nodes and source != START:
                raise GraphValidationError(f"Edge references an unregistered node: '{source}'.")
            if target not in self._nodes and target != END:
                raise GraphValidationError(f"Edge references an unregistered node: '{target}'.")

    def compile(self, checkpointer: BaseCheckpointSaver[Any] | None = None) -> CompiledGraph:
        """Validate and compile the graph.

        ``checkpointer`` enables LangGraph's native pause/resume: without
        one, ``interrupt_before``/``interrupt_after`` still stop the run,
        but nothing can resume it afterward (LangGraph has nowhere to
        read the paused state back from). See the Human-in-the-Loop
        Execution Architecture README section for how this powers
        ``ExecutionEngine.resume()``.
        """
        self.validate()
        compiled = self._graph.compile(
            checkpointer=checkpointer,
            interrupt_before=self._config.interrupt_before or None,
            interrupt_after=self._config.interrupt_after or None,
            debug=self._config.debug,
        )
        return CompiledGraph(
            compiled=compiled,
            nodes=dict(self._nodes),
            edges=list(self._edges),
            entry_point=self._entry_point,
            config=self._config,
            has_checkpointer=checkpointer is not None,
        )

    def export(self) -> GraphMetadata:
        """Return a LangGraph-independent structural snapshot of this graph."""
        return GraphMetadata.from_graph(self._nodes, self._edges, self._entry_point)

    def _wrap(self, node: OrchestrationNode) -> Callable[[InsightPilotState], Awaitable[dict[str, Any]]]:
        async def _run(state: InsightPilotState) -> dict[str, Any]:
            await self._event_bus.emit(
                NodeStarted(execution_id=state.execution_id, timestamp=utc_now(), node_name=node.name)
            )
            start = time.perf_counter()
            with agent_context(node.name):
                updated_state = await node.execute(state)
            duration_ms = (time.perf_counter() - start) * 1000
            await self._event_bus.emit(
                NodeCompleted(
                    execution_id=state.execution_id,
                    timestamp=utc_now(),
                    node_name=node.name,
                    duration_ms=duration_ms,
                )
            )
            return updated_state.model_dump()

        return _run
