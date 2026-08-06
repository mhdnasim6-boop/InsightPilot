"""ProgressTracker: derived, read-only progress computed from an ExecutionState.

A pure aggregator, mirroring ``MetricsService``'s own "stateless,
recomputed on every call" design (Observability & Tracing Architecture) —
nothing here is stored; every field is computed fresh from whatever
``ExecutionState`` is passed in.
"""

from pydantic import BaseModel, Field

from backend.execution.state.execution_state import ExecutionState
from backend.execution.state.node_status import NodeStatus


class ProgressSnapshot(BaseModel):
    """A point-in-time progress summary of one DAG execution."""

    execution_id: str
    plan_id: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    progress_percent: float
    pending: list[str] = Field(default_factory=list)
    queued: list[str] = Field(default_factory=list)
    running: list[str] = Field(default_factory=list)
    completed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    paused: list[str] = Field(default_factory=list)
    cancelled: list[str] = Field(default_factory=list)


class ProgressTracker:
    """Computes a ProgressSnapshot from an ExecutionState."""

    def snapshot(self, state: ExecutionState) -> ProgressSnapshot:
        """Return ``state``'s current progress — counts, percent complete, and per-status step lists."""
        total = len(state.steps)
        completed = state.step_ids_with_status(NodeStatus.COMPLETED)
        failed = state.step_ids_with_status(NodeStatus.FAILED)
        cancelled = state.step_ids_with_status(NodeStatus.CANCELLED)
        settled = len(completed) + len(failed) + len(cancelled)
        percent = round((settled / total) * 100, 1) if total else 100.0

        return ProgressSnapshot(
            execution_id=state.execution_id,
            plan_id=state.plan_id,
            total_steps=total,
            completed_steps=len(completed),
            failed_steps=len(failed),
            progress_percent=percent,
            pending=state.step_ids_with_status(NodeStatus.PENDING),
            queued=state.step_ids_with_status(NodeStatus.QUEUED),
            running=state.step_ids_with_status(NodeStatus.RUNNING),
            completed=completed,
            failed=failed,
            paused=state.step_ids_with_status(NodeStatus.PAUSED),
            cancelled=cancelled,
        )
