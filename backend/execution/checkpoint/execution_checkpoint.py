"""ExecutionCheckpoint: an immutable, point-in-time snapshot of an ExecutionState,
taken after every scheduler tick — the mechanism ``ExecutionService.resume()``
continues from.

A checkpoint holds the *actual* ``ExecutionState`` (completed steps, their
stored results/"artifacts", which steps are paused on an approval, which
failed) rather than a separate derived representation — resuming can
never drift from what genuinely happened. ``ExecutionCheckpointStore``
mirrors ``TraceStore``'s "plain dict, process-wide, no persistence
backend yet" convention: it holds only the latest checkpoint per
execution_id, not a full history log, since resuming only ever needs
"where things stand right now."

The checkpoint also carries the originating ``plan`` — deliberately not
just its ``plan_id`` — so ``ExecutionService`` never needs its own
per-instance ``dict[execution_id, ExecutionPlan]``. That matters because
``ExecutionService`` itself is intentionally *not* cached across requests
(mirroring ``FileAgentService``/every other agent service: a stateless
wrapper whose only state lives in an already-cached store); a
``DependencyResolver`` is cheap and pure to rebuild from ``plan`` on
demand, so nothing about resuming or graph-rendering depends on the same
``ExecutionService`` Python object having served the original request.
"""

from datetime import datetime

from pydantic import BaseModel

from backend.execution.state.execution_state import ExecutionState
from backend.planning.models.plan import ExecutionPlan


class ExecutionCheckpoint(BaseModel):
    """The latest known state of one DAG execution, checkpointed for resume."""

    execution_id: str
    plan_id: str
    plan: ExecutionPlan
    state: ExecutionState
    checkpointed_at: datetime


class ExecutionCheckpointStore:
    """Process-wide store of the latest ExecutionCheckpoint per execution_id."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, ExecutionCheckpoint] = {}

    def put(self, checkpoint: ExecutionCheckpoint) -> None:
        """Store (or overwrite) a checkpoint, keyed by its own ``execution_id``."""
        self._checkpoints[checkpoint.execution_id] = checkpoint

    def get(self, execution_id: str) -> ExecutionCheckpoint | None:
        """Return the latest checkpoint for an execution_id, or None if not present."""
        return self._checkpoints.get(execution_id)

    def list_all(self) -> list[ExecutionCheckpoint]:
        """Return every stored checkpoint, most recently checkpointed first."""
        return list(reversed(self._checkpoints.values()))

    def list_for_plan(self, plan_id: str) -> list[ExecutionCheckpoint]:
        """Return every checkpoint for a given plan_id, most recently checkpointed first."""
        return [checkpoint for checkpoint in self.list_all() if checkpoint.plan_id == plan_id]
