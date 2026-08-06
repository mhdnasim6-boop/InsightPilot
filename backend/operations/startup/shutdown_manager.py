"""ShutdownManager: runs a fixed, ordered sequence of shutdown stages —
the reverse of StartupManager's own order — recording each one's outcome.

Its own independent stage/result/report shapes (only the trivial, two-
value ``StageStatus`` vocabulary is shared with StartupManager, since
"completed or failed" is universal) — the two managers are structurally
similar but conceptually distinct concerns, each owning only its own
stage's results, per this phase's "every operational concern must have
exactly one owner." Like StartupManager, a stage raising never stops the
remaining stages: one service's failure to close cleanly must never
prevent the others from shutting down gracefully.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

from backend.operations.startup.startup_manager import StageStatus
from backend.utils.time import utc_now


@dataclass(frozen=True)
class ShutdownStage:
    """One named shutdown step: a human-readable ``name`` and the callable that performs it."""

    name: str
    action: Callable[[], object]


class ShutdownStageResult(BaseModel):
    """The recorded outcome of one shutdown stage."""

    name: str
    status: StageStatus
    duration_ms: float
    error: str | None = None


class ShutdownReport(BaseModel):
    """The full outcome of one ``ShutdownManager.run()`` call."""

    stages: list[ShutdownStageResult] = Field(default_factory=list)
    completed: bool
    started_at: datetime
    finished_at: datetime


class ShutdownManager:
    """Runs its configured stages in order (caller-supplied, already reverse of startup), never raising."""

    def __init__(self, stages: Sequence[ShutdownStage]) -> None:
        self._stages = list(stages)

    def run(self) -> ShutdownReport:
        """Run every configured stage in order and record the result."""
        started_at = utc_now()
        results = [self._run_stage(stage) for stage in self._stages]
        finished_at = utc_now()
        return ShutdownReport(
            stages=results,
            completed=all(result.status == StageStatus.COMPLETED for result in results),
            started_at=started_at,
            finished_at=finished_at,
        )

    def _run_stage(self, stage: ShutdownStage) -> ShutdownStageResult:
        start = time.perf_counter()
        try:
            stage.action()
        except Exception as exc:  # noqa: BLE001 - one stage's failure must never block the rest from shutting down
            duration_ms = (time.perf_counter() - start) * 1000
            return ShutdownStageResult(
                name=stage.name, status=StageStatus.FAILED, duration_ms=duration_ms,
                error=f"{type(exc).__name__}: {exc}",
            )
        duration_ms = (time.perf_counter() - start) * 1000
        return ShutdownStageResult(name=stage.name, status=StageStatus.COMPLETED, duration_ms=duration_ms)
