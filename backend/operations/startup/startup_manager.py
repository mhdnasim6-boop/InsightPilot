"""StartupManager: runs a fixed, ordered sequence of startup stages and
records each one's outcome.

This class owns only ordering, timing, and failure containment — never
which services exist or how they're constructed. Every stage's ``action``
is a plain, already-existing callable (a bound method on an
already-constructed singleton, or a small closure over one) handed in by
the caller — see ``backend.dependencies.operations.get_startup_manager``,
which wires the concrete "Configuration -> Plugin loading -> Registries
-> Memory -> Observability -> Execution -> API ready" sequence this
phase's own spec names, entirely out of services that already exist.

A stage raising never stops the remaining stages from running (mirrors
``backend.plugins.registry.PluginRegistry``'s own "one bad plugin/stage
must never crash the platform" philosophy) — a caller who wants every
possible problem reported at once needs every stage attempted, not just
the first failure. Whether the *overall* run counts as ready is up to
whoever reads the returned ``StartupReport`` (``ReadinessService``), not
this class.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from backend.utils.time import utc_now


class StageStatus(str, Enum):
    """Outcome of one startup stage."""

    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class StartupStage:
    """One named startup step: a human-readable ``name`` and the callable that performs it."""

    name: str
    action: Callable[[], object]


class StartupStageResult(BaseModel):
    """The recorded outcome of one startup stage."""

    name: str
    status: StageStatus
    duration_ms: float
    error: str | None = None


class StartupReport(BaseModel):
    """The full outcome of one ``StartupManager.run()`` call."""

    profile: str
    stages: list[StartupStageResult] = Field(default_factory=list)
    completed: bool
    started_at: datetime
    finished_at: datetime


class StartupManager:
    """Runs its configured stages in order, recording (never raising) each outcome."""

    def __init__(self, stages: Sequence[StartupStage]) -> None:
        self._stages = list(stages)
        self._last_report: StartupReport | None = None

    def run(self, profile: str) -> StartupReport:
        """Run every configured stage in order and record the result. Idempotent — safe to call again."""
        started_at = utc_now()
        results: list[StartupStageResult] = []
        for stage in self._stages:
            results.append(self._run_stage(stage))
        finished_at = utc_now()

        report = StartupReport(
            profile=profile,
            stages=results,
            completed=all(result.status == StageStatus.COMPLETED for result in results),
            started_at=started_at,
            finished_at=finished_at,
        )
        self._last_report = report
        return report

    @property
    def last_report(self) -> StartupReport | None:
        """The most recent ``run()``'s report, or None if ``run()`` has never been called."""
        return self._last_report

    def _run_stage(self, stage: StartupStage) -> StartupStageResult:
        start = time.perf_counter()
        try:
            stage.action()
        except Exception as exc:  # noqa: BLE001 - one failed stage must never stop the rest, or crash startup
            duration_ms = (time.perf_counter() - start) * 1000
            return StartupStageResult(
                name=stage.name, status=StageStatus.FAILED, duration_ms=duration_ms,
                error=f"{type(exc).__name__}: {exc}",
            )
        duration_ms = (time.perf_counter() - start) * 1000
        return StartupStageResult(name=stage.name, status=StageStatus.COMPLETED, duration_ms=duration_ms)
