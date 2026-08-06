"""CollaborationService: the only public entry point for the collaboration layer.

``create_session()``/``run()``/``delegate()``/``resume()``/``cancel()``/
``history()``/``statistics()`` — nothing outside ``backend/collaboration/``
should import ``CollaborationStore``/``CollaborationCoordinator``/
``CollaborationExecutor`` directly. ``discover_capabilities()`` is the
seam ``PlannerAgent`` now queries instead of reading ``GraphBuilder``
itself (see ``backend.agents.planner.execution.planner_agent``).

Every public operation here is recorded as a ``ToolTrace`` via the
*existing* ``ObservabilityService.record_tool_trace()`` — the exact
mechanism ``MemoryService`` already reuses for the same reason — so
messages/delegations/subtasks/artifact-routing that happen transitively
inside ``delegate()``/``run()``/``resume()`` are all covered by that one
call's trace, with no second tracing implementation. A terminal session
(COMPLETED/FAILED/CANCELLED) is remembered as one ``MemoryType.COLLABORATION``
memory via the *existing* ``MemoryService`` — mirroring exactly how
``ExecutionService._remember_execution()`` remembers one summary per
terminal DAG execution, not one memory per step.
"""

import time
from datetime import datetime
from typing import Any

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.execution.collaboration_executor import CollaborationExecutor
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.agent_capability import AgentCapability
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.models.collaboration_statistics import (
    CollaborationStatistics,
)
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.execution.state.node_status import NodeStatus
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.observability.context import current_agent_name
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now

_TERMINAL = frozenset({PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED})
_COMPLETED_ONLY = (NodeStatus.COMPLETED,)
_FAILED_ONLY = (NodeStatus.FAILED, NodeStatus.CANCELLED)


class CollaborationService:
    """Runs autonomous, structured multi-agent collaboration sessions."""

    def __init__(
        self,
        coordinator: CollaborationCoordinator,
        executor: CollaborationExecutor,
        capability_registry: AgentCapabilityRegistry,
        message_bus: MessageBus,
        observability_service: ObservabilityService | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._executor = executor
        self._capability_registry = capability_registry
        self._message_bus = message_bus
        self._observability_service = observability_service
        self._memory_service = memory_service

    def discover_capabilities(self) -> list[AgentCapability]:
        """Every registered agent's declared inputs/outputs/tools/cost/duration."""
        return self._capability_registry.discover()

    def create_session(self, request: CollaborationRequest) -> CollaborationTask:
        """Start a new collaboration session for a high-level goal — no subtasks yet."""
        start_time, start = utc_now(), time.perf_counter()
        task = self._coordinator.create_session(request)
        self._trace("collaboration.create_session", start_time, start, ExecutionStatus.COMPLETED)
        return task

    def delegate(
        self,
        collaboration_id: str,
        assigned_agent: str,
        description: str,
        inputs: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        reason: str = "",
    ) -> SubTask:
        """Assign a new SubTask to ``assigned_agent`` (or reuse an existing equivalent one)."""
        start_time, start = utc_now(), time.perf_counter()
        subtask = self._coordinator.delegate(collaboration_id, assigned_agent, description, inputs, dependencies, reason)
        self._trace("collaboration.delegate", start_time, start, ExecutionStatus.COMPLETED)
        return subtask

    async def run(self, collaboration_id: str) -> CollaborationTask:
        """Run every currently-ready (and dynamically spawned) subtask to completion or a pause."""
        start_time, start = utc_now(), time.perf_counter()
        task = await self._executor.run(collaboration_id)
        self._trace("collaboration.run", start_time, start, ExecutionStatus.COMPLETED)
        self._remember_session(task)
        return task

    async def resume(self, collaboration_id: str) -> CollaborationTask:
        """Resume a PAUSED collaboration session, then keep driving it."""
        start_time, start = utc_now(), time.perf_counter()
        task = await self._executor.resume(collaboration_id)
        self._trace("collaboration.resume", start_time, start, ExecutionStatus.COMPLETED)
        self._remember_session(task)
        return task

    def cancel(self, collaboration_id: str) -> CollaborationTask:
        """Cancel a collaboration session outright."""
        start_time, start = utc_now(), time.perf_counter()
        task = self._executor.cancel(collaboration_id)
        self._trace("collaboration.cancel", start_time, start, ExecutionStatus.COMPLETED)
        self._remember_session(task)
        return task

    def get(self, collaboration_id: str) -> CollaborationTask:
        """Fetch a collaboration session's current task graph."""
        return self._coordinator.get(collaboration_id)

    def list_sessions(self) -> list[CollaborationTask]:
        """Every tracked collaboration session."""
        return self._coordinator.store.list_tasks()

    def history(self, collaboration_id: str) -> dict[str, Any]:
        """Every message, delegation, negotiation, and artifact exchange for one session."""
        store = self._coordinator.store
        return {
            "messages": store.list_messages(collaboration_id),
            "delegations": store.list_delegations(collaboration_id),
            "negotiations": store.list_negotiations(collaboration_id),
            "artifact_exchanges": store.list_exchanges(collaboration_id),
        }

    def statistics(self) -> CollaborationStatistics:
        """Aggregate counts across every tracked collaboration session."""
        store = self._coordinator.store
        sessions = store.list_tasks()
        by_status: dict[str, int] = {}
        total_subtasks = 0
        total_messages = 0
        total_delegations = 0
        total_negotiations = 0
        for session in sessions:
            by_status[session.status.value] = by_status.get(session.status.value, 0) + 1
            total_subtasks += len(session.subtasks)
            total_messages += len(store.list_messages(session.collaboration_id))
            total_delegations += len(store.list_delegations(session.collaboration_id))
            total_negotiations += len(store.list_negotiations(session.collaboration_id))
        return CollaborationStatistics(
            total_sessions=len(sessions),
            by_status=by_status,
            total_subtasks=total_subtasks,
            total_messages=total_messages,
            total_delegations=total_delegations,
            total_negotiations=total_negotiations,
            average_subtasks_per_session=(total_subtasks / len(sessions)) if sessions else 0.0,
        )

    def _remember_session(self, task: CollaborationTask) -> None:
        if self._memory_service is None or task.status not in _TERMINAL:
            return
        completed = task.subtask_ids_with_status(*_COMPLETED_ONLY)
        failed = task.subtask_ids_with_status(*_FAILED_ONLY)
        history = self.history(task.collaboration_id)
        self._memory_service.remember(
            title=f"Collaboration: {task.goal[:60]}",
            summary=f"{len(completed)} subtask(s) completed, {len(failed)} failed.",
            memory_type=MemoryType.COLLABORATION,
            scope=MemoryScope.PROJECT,
            content={
                "collaboration_id": task.collaboration_id,
                "status": task.status.value,
                "completed_subtasks": completed,
                "failed_subtasks": failed,
                "total_messages": len(history["messages"]),
                "total_delegations": len(history["delegations"]),
            },
            tags=["collaboration"],
            references=[MemoryReference(reference_type="collaboration", reference_id=task.collaboration_id)],
            metadata={"session_id": task.session_id},
        )

    def _trace(self, operation_name: str, start_time: datetime, start: float, status: ExecutionStatus) -> None:
        if self._observability_service is None:
            return
        self._observability_service.record_tool_trace(
            ToolTrace(
                tool_name=operation_name,
                agent_name=current_agent_name.get(),
                start_time=start_time,
                end_time=utc_now(),
                duration_ms=(time.perf_counter() - start) * 1000,
                status=status,
            )
        )
