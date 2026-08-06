"""DependencyNegotiator: dedupes subtasks that would produce the identical artifact.

If two subtasks would run the same agent with the identical inputs, they
are asking for the same artifact — the coordinator runs the producer
only once and reuses its result for every other requester, recording a
``NegotiationDecision`` for each dedup.
"""

from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.collaboration.models.negotiation import NegotiationDecision
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


def _signature(assigned_agent: str, inputs: dict[str, object]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (assigned_agent, tuple(sorted((str(key), str(value)) for key, value in inputs.items())))


class DependencyNegotiator:
    """Finds an existing subtask that already covers a new artifact need, if any."""

    def __init__(self, store: CollaborationStore) -> None:
        self._store = store

    def find_existing_producer(
        self, task: CollaborationTask, assigned_agent: str, inputs: dict[str, object]
    ) -> SubTask | None:
        """Return an already-present subtask with the identical (agent, inputs) signature, if any."""
        signature = _signature(assigned_agent, inputs)
        for subtask in task.subtasks.values():
            if _signature(subtask.assigned_agent, subtask.inputs) == signature:
                return subtask
        return None

    def record_decision(
        self, collaboration_id: str, requested_by: list[str], resolved_producer_subtask_id: str, reason: str
    ) -> NegotiationDecision:
        """Record that ``requested_by`` all reuse ``resolved_producer_subtask_id``'s result."""
        decision = NegotiationDecision(
            negotiation_id=generate_id(),
            collaboration_id=collaboration_id,
            requested_by=requested_by,
            resolved_producer_subtask_id=resolved_producer_subtask_id,
            reason=reason,
            created_at=utc_now(),
        )
        self._store.add_negotiation(decision)
        return decision
