"""Runs compiled orchestration graphs.

Tracks in-flight executions in memory (no *domain-level* checkpoint
persistence yet — see ``backend.orchestration.checkpoints``) and emits
ExecutionStarted / ExecutionCompleted / ExecutionFailed events around
every run. Since Phase 23 (Human-in-the-Loop), every run is tied to a
LangGraph thread keyed by its own ``execution_id`` — if the compiled
graph carries a checkpointer and an ``interrupt_before`` node is
reached, ``ainvoke``/``astream`` simply return the state as of just
before that node (no exception, no special-casing needed here) and
``resume()``/``get_next_nodes()`` can later continue or inspect that
same paused thread.
"""

import asyncio
import time
from collections.abc import AsyncIterator

from langchain_core.runnables import RunnableConfig
from loguru import logger

from backend.orchestration.events.bus import EventBus
from backend.orchestration.events.events import (
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
)
from backend.orchestration.exceptions import CheckpointNotConfiguredError
from backend.orchestration.graph.compiled import CompiledGraph
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.utils.time import utc_now


class ExecutionEngine:
    """Runs, streams, cancels, resumes, and inspects orchestration graph executions."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._states: dict[str, InsightPilotState] = {}
        self._tasks: dict[str, asyncio.Task[InsightPilotState]] = {}
        self._graphs: dict[str, CompiledGraph] = {}

    async def run(self, graph: CompiledGraph, state: InsightPilotState) -> InsightPilotState:
        """Run a graph to completion — or until it pauses at an interrupt point — and return that state."""
        self._graphs[state.execution_id] = graph
        await self._event_bus.emit(
            ExecutionStarted(execution_id=state.execution_id, timestamp=utc_now(), session_id=state.session_id)
        )
        start = time.perf_counter()
        task = asyncio.create_task(self._invoke(graph, state))
        self._tasks[state.execution_id] = task
        try:
            result_state = await task
            self._states[state.execution_id] = result_state
            duration_ms = (time.perf_counter() - start) * 1000
            await self._event_bus.emit(
                ExecutionCompleted(
                    execution_id=state.execution_id,
                    timestamp=utc_now(),
                    status=result_state.status.value,
                    duration_ms=duration_ms,
                )
            )
            return result_state
        except asyncio.CancelledError:
            cancelled_state = state.model_copy(update={"status": ExecutionStatus.CANCELLED, "updated_at": utc_now()})
            self._states[state.execution_id] = cancelled_state
            await self._event_bus.emit(
                ExecutionFailed(
                    execution_id=state.execution_id,
                    timestamp=utc_now(),
                    error="Execution was cancelled.",
                    failed_node=state.current_node,
                )
            )
            raise
        except Exception as exc:
            logger.exception("Execution '{}' failed", state.execution_id)
            failed_state = state.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "errors": [*state.errors, str(exc)],
                    "updated_at": utc_now(),
                }
            )
            self._states[state.execution_id] = failed_state
            await self._event_bus.emit(
                ExecutionFailed(
                    execution_id=state.execution_id,
                    timestamp=utc_now(),
                    error=str(exc),
                    failed_node=state.current_node,
                )
            )
            raise
        finally:
            self._tasks.pop(state.execution_id, None)

    async def stream(self, graph: CompiledGraph, state: InsightPilotState) -> AsyncIterator[InsightPilotState]:
        """Stream state after each node completes."""
        self._graphs[state.execution_id] = graph
        await self._event_bus.emit(
            ExecutionStarted(execution_id=state.execution_id, timestamp=utc_now(), session_id=state.session_id)
        )
        start = time.perf_counter()
        try:
            async for update in graph.compiled.astream(
                state, config=self._thread_config(graph, state.execution_id), stream_mode="values"
            ):
                result_state = InsightPilotState.model_validate(update)
                self._states[state.execution_id] = result_state
                yield result_state

            duration_ms = (time.perf_counter() - start) * 1000
            final_state = self._states.get(state.execution_id, state)
            await self._event_bus.emit(
                ExecutionCompleted(
                    execution_id=state.execution_id,
                    timestamp=utc_now(),
                    status=final_state.status.value,
                    duration_ms=duration_ms,
                )
            )
        except Exception as exc:
            logger.exception("Streamed execution '{}' failed", state.execution_id)
            await self._event_bus.emit(
                ExecutionFailed(
                    execution_id=state.execution_id,
                    timestamp=utc_now(),
                    error=str(exc),
                    failed_node=state.current_node,
                )
            )
            raise

    def cancel(self, execution_id: str) -> bool:
        """Cancel a tracked in-flight execution (started via ``run``). Returns True if cancelled."""
        task = self._tasks.get(execution_id)
        if task is None or task.done():
            return False
        return task.cancel()

    async def resume(self, execution_id: str) -> InsightPilotState:
        """Resume a previously paused (interrupted) execution from its own checkpoint.

        Raises ``CheckpointNotConfiguredError`` if ``execution_id`` was
        never run through this engine, or if the graph it ran on was
        compiled without a checkpointer — LangGraph has nothing to
        resume *from* in that case. Safe to call on an execution that
        has already run to completion: LangGraph's own checkpoint simply
        has no pending node, and the unchanged final state is returned.
        """
        graph = self._graphs.get(execution_id)
        if graph is None or not graph.has_checkpointer:
            raise CheckpointNotConfiguredError(
                f"Cannot resume execution '{execution_id}': no checkpoint implementation is configured."
            )
        raw_result = await graph.compiled.ainvoke(None, config=self._thread_config(graph, execution_id))
        result_state = InsightPilotState.model_validate(raw_result)
        self._states[execution_id] = result_state
        return result_state

    async def get_next_nodes(self, execution_id: str) -> tuple[str, ...]:
        """Return the node name(s) that would run next if resumed — empty if complete or unknown.

        A non-empty result means ``execution_id``'s graph run is
        genuinely paused at an interrupt point, not merely slow or
        still in flight.
        """
        graph = self._graphs.get(execution_id)
        if graph is None or not graph.has_checkpointer:
            return ()
        snapshot = await graph.compiled.aget_state(self._thread_config(graph, execution_id))
        return tuple(snapshot.next)

    def inspect(self, execution_id: str) -> InsightPilotState | None:
        """Return the last known state for a tracked execution, or None."""
        return self._states.get(execution_id)

    def _thread_config(self, graph: CompiledGraph, execution_id: str) -> RunnableConfig:
        return RunnableConfig(
            recursion_limit=graph.config.max_iterations,
            configurable={"thread_id": execution_id},
        )

    async def _invoke(self, graph: CompiledGraph, state: InsightPilotState) -> InsightPilotState:
        raw_result = await graph.compiled.ainvoke(state, config=self._thread_config(graph, state.execution_id))
        return InsightPilotState.model_validate(raw_result)
