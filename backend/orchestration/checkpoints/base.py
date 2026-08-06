"""Abstract contract for persisting and restoring orchestration state.

No implementation in this phase. Future implementations (in-memory,
SQLite, Redis, Postgres) each satisfy this same contract, so
``ExecutionEngine.resume()`` — and whatever wires a checkpointer in
later — never needs to change based on which backend is configured.
"""

from abc import ABC, abstractmethod

from backend.orchestration.state.state import InsightPilotState


class CheckpointInterface(ABC):
    """Storage-agnostic contract for saving/restoring execution state snapshots."""

    @abstractmethod
    async def save(self, execution_id: str, state: InsightPilotState) -> None:
        """Persist a snapshot of the given execution's state."""

    @abstractmethod
    async def load(self, execution_id: str) -> InsightPilotState | None:
        """Return the most recently saved state for an execution, or None."""

    @abstractmethod
    async def list_checkpoints(self, execution_id: str) -> list[InsightPilotState]:
        """Return all saved snapshots for an execution, oldest first."""

    @abstractmethod
    async def delete(self, execution_id: str) -> bool:
        """Remove all saved snapshots for an execution. Returns True if any existed."""
