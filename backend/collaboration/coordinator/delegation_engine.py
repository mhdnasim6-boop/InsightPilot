"""DelegationEngine: assigns a SubTask to an agent, recording why.

Every delegation is both a ``Delegation`` record (for
``CollaborationService.history()``) and a ``MessageType.DELEGATION_REQUEST``
message sent through the ``MessageBus`` — agents never call each other
directly, so "assigning work" and "notifying the assignee" are the same
act here.
"""

from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_message import MessageType
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.collaboration.models.delegation import Delegation
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.execution.state.node_status import NodeStatus
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class DelegationEngine:
    """Creates SubTasks, assigns them to agents, and records the delegation."""

    def __init__(self, store: CollaborationStore, message_bus: MessageBus) -> None:
        self._store = store
        self._message_bus = message_bus

    def delegate(
        self,
        task: CollaborationTask,
        assigned_agent: str,
        description: str,
        inputs: dict[str, object] | None = None,
        dependencies: list[str] | None = None,
        reason: str = "",
        from_agent: str = "coordinator",
        requested_by: str | None = None,
    ) -> tuple[CollaborationTask, SubTask]:
        """Create a new SubTask, assign it to ``assigned_agent``, and record the delegation.

        Returns the updated task (with the new SubTask added, in PENDING
        status) and the SubTask itself.
        """
        subtask = SubTask(
            subtask_id=generate_id(),
            description=description,
            assigned_agent=assigned_agent,
            inputs=inputs or {},
            dependencies=dependencies or [],
            status=NodeStatus.PENDING,
            requested_by=requested_by,
        )
        updated_task = task.model_copy(
            update={
                "subtasks": {**task.subtasks, subtask.subtask_id: subtask},
                "subtask_order": [*task.subtask_order, subtask.subtask_id],
                "updated_at": utc_now(),
            }
        )
        self._record_delegation(task.collaboration_id, subtask.subtask_id, from_agent, assigned_agent, reason)
        return updated_task, subtask

    def _record_delegation(
        self, collaboration_id: str, subtask_id: str, from_agent: str, to_agent: str, reason: str
    ) -> None:
        delegation = Delegation(
            delegation_id=generate_id(),
            collaboration_id=collaboration_id,
            subtask_id=subtask_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            created_at=utc_now(),
        )
        self._store.add_delegation(delegation)
        self._message_bus.send(
            collaboration_id,
            from_agent,
            to_agent,
            MessageType.DELEGATION_REQUEST,
            {"subtask_id": subtask_id, "reason": reason},
        )
