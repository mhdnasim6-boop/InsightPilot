"""In-memory plan_id -> ExecutionHistoryEvent[] store: an append-only timeline per plan."""

from collections import defaultdict

from backend.approval.models.history import ExecutionHistoryEvent


class ExecutionHistoryStore:
    """Process-wide, append-only store of ExecutionHistoryEvents, keyed by plan_id."""

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionHistoryEvent]] = defaultdict(list)

    def append(self, event: ExecutionHistoryEvent) -> None:
        """Append one event to its plan's timeline."""
        self._events[event.plan_id].append(event)

    def list_for_plan(self, plan_id: str) -> list[ExecutionHistoryEvent]:
        """Return a plan's full timeline, oldest first."""
        return list(self._events[plan_id])
