"""CollaborationCoordinator: owns the task graph, agent assignments, artifact
routing, and status for every collaboration session.

Every mutation replaces the ``CollaborationTask`` snapshot in
``CollaborationStore`` wholesale (``model_copy``, never in-place),
mirroring ``DAGScheduler``'s own snapshot discipline. Never dispatches
any agent itself — that is ``CollaborationExecutor``'s job, layered on
top of this class plus the existing ``ExecutionService``.
"""

from typing import Any

from backend.collaboration.coordinator.artifact_router import ArtifactRouter
from backend.collaboration.coordinator.delegation_engine import DelegationEngine
from backend.collaboration.coordinator.dependency_negotiator import DependencyNegotiator
from backend.collaboration.exceptions import (
    CollaborationNotFoundError,
    SubTaskNotFoundError,
)
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.artifact_exchange import ArtifactExchange
from backend.collaboration.models.collaboration_message import MessageType
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class CollaborationCoordinator:
    """Creates sessions, delegates/spawns subtasks, routes artifacts, and tracks status."""

    def __init__(
        self,
        store: CollaborationStore,
        message_bus: MessageBus,
        delegation_engine: DelegationEngine,
        negotiator: DependencyNegotiator,
        artifact_router: ArtifactRouter,
    ) -> None:
        self._store = store
        self._message_bus = message_bus
        self._delegation_engine = delegation_engine
        self._negotiator = negotiator
        self._artifact_router = artifact_router

    @property
    def store(self) -> CollaborationStore:
        """The underlying CollaborationStore — read-only history/statistics access only."""
        return self._store

    def create_session(self, request: CollaborationRequest) -> CollaborationTask:
        """Start a new, empty collaboration session for a high-level goal."""
        now = utc_now()
        task = CollaborationTask(
            collaboration_id=generate_id(),
            session_id=request.session_id,
            goal=request.goal,
            status=PlanStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        self._store.put_task(task)
        return task

    def delegate(
        self,
        collaboration_id: str,
        assigned_agent: str,
        description: str,
        inputs: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        reason: str = "",
        requested_by: str | None = None,
    ) -> SubTask:
        """Assign a new SubTask to ``assigned_agent``, deduplicating an identical existing one.

        If an existing subtask already asks the same agent to do the
        same work (identical inputs), that subtask is reused and a
        NegotiationDecision is recorded instead of creating a duplicate.
        """
        task = self.get(collaboration_id)
        inputs = inputs or {}
        existing = self._negotiator.find_existing_producer(task, assigned_agent, inputs)
        if existing is not None:
            self._negotiator.record_decision(
                collaboration_id,
                requested_by=[requested_by or "caller"],
                resolved_producer_subtask_id=existing.subtask_id,
                reason=f"Reusing existing '{assigned_agent}' subtask with identical inputs.",
            )
            return existing

        updated_task, subtask = self._delegation_engine.delegate(
            task, assigned_agent, description, inputs, dependencies, reason, requested_by=requested_by
        )
        self._store.put_task(updated_task)
        return subtask

    def spawn_subtask(
        self,
        collaboration_id: str,
        requested_by_subtask_id: str,
        assigned_agent: str,
        description: str,
        inputs: dict[str, Any] | None = None,
        reason: str = "",
    ) -> SubTask:
        """Add a new SubTask requested by an already-running/completed subtask.

        This is how the execution graph expands dynamically: a subtask's
        own result can ask for follow-up work without PlannerAgent ever
        having enumerated it up front.
        """
        subtask = self.delegate(
            collaboration_id,
            assigned_agent,
            description,
            inputs,
            dependencies=[requested_by_subtask_id],
            reason=reason,
            requested_by=requested_by_subtask_id,
        )
        self._message_bus.send(
            collaboration_id,
            requested_by_subtask_id,
            assigned_agent,
            MessageType.SUBTASK_REQUEST,
            {"subtask_id": subtask.subtask_id, "reason": reason},
        )
        return subtask

    def receive_result(
        self, collaboration_id: str, subtask_id: str, status: NodeStatus, result: dict[str, Any] | None, error: str | None
    ) -> CollaborationTask:
        """Record a subtask's outcome and broadcast that its artifact (if any) is ready."""
        task = self.get(collaboration_id)
        subtask = self._require_subtask(task, subtask_id)
        updated_subtask = subtask.model_copy(update={"status": status, "result": result, "error": error})
        updated_task = task.model_copy(
            update={"subtasks": {**task.subtasks, subtask_id: updated_subtask}, "updated_at": utc_now()}
        )
        self._store.put_task(updated_task)
        if result is not None:
            self._message_bus.broadcast(
                collaboration_id, subtask.assigned_agent, MessageType.ARTIFACT_READY, {"subtask_id": subtask_id}
            )
        return updated_task

    def runnable_subtasks(self, task: CollaborationTask) -> list[SubTask]:
        """Every PENDING subtask whose dependencies have all COMPLETED, in declaration order."""
        completed = set(task.subtask_ids_with_status(NodeStatus.COMPLETED))
        return [
            task.subtasks[subtask_id]
            for subtask_id in task.subtask_order
            if task.subtasks[subtask_id].status == NodeStatus.PENDING
            and all(dependency in completed for dependency in task.subtasks[subtask_id].dependencies)
        ]

    def route_inputs(self, task: CollaborationTask, subtask: SubTask) -> dict[str, Any]:
        """Merge every dependency's produced artifacts into ``subtask``'s own declared inputs.

        Records one ``ArtifactExchange`` per producer whose fields were
        actually used — the audit trail behind "Example artifact routing."
        """
        producers = {
            other.subtask_id: (other.assigned_agent, other.result)
            for other in task.subtasks.values()
            if other.result is not None
        }
        routed, filled_by_producer = self._artifact_router.route_all(producers, subtask.inputs, subtask.dependencies)
        for producer_subtask_id, artifact_keys in filled_by_producer.items():
            self._store.add_exchange(
                ArtifactExchange(
                    exchange_id=generate_id(),
                    collaboration_id=task.collaboration_id,
                    producer_subtask_id=producer_subtask_id,
                    consumer_subtask_id=subtask.subtask_id,
                    artifact_keys=artifact_keys,
                    created_at=utc_now(),
                )
            )
        return routed

    def finish(self, collaboration_id: str, status: PlanStatus) -> CollaborationTask:
        """Mark a collaboration session terminal (or paused)."""
        task = self.get(collaboration_id)
        updated = task.model_copy(update={"status": status, "updated_at": utc_now()})
        self._store.put_task(updated)
        return updated

    def update(self, task: CollaborationTask) -> CollaborationTask:
        """Persist an already-built task snapshot (used by CollaborationExecutor mid-run)."""
        self._store.put_task(task)
        return task

    def get(self, collaboration_id: str) -> CollaborationTask:
        """Fetch a collaboration session's current task graph. Raises CollaborationNotFoundError if unknown."""
        task = self._store.get_task(collaboration_id)
        if task is None:
            raise CollaborationNotFoundError(f"No collaboration session found for '{collaboration_id}'.")
        return task

    def _require_subtask(self, task: CollaborationTask, subtask_id: str) -> SubTask:
        subtask = task.subtasks.get(subtask_id)
        if subtask is None:
            raise SubTaskNotFoundError(f"No subtask '{subtask_id}' in collaboration '{task.collaboration_id}'.")
        return subtask
