"""ReadinessService: "is this process ready to serve real traffic."

Reads ``StartupManager``'s own last report rather than re-checking
anything itself — ``StartupManager`` is the one owner of "did every
startup stage complete" (rule 4: "every operational concern must have
exactly one owner"). This is exactly the textbook Kubernetes-style split:
liveness answers "should this container be restarted," readiness answers
"should this container receive traffic right now" — a container can be
alive but not yet (or no longer) ready.
"""

from pydantic import BaseModel, Field

from backend.operations.startup.startup_manager import (
    StartupManager,
    StartupStageResult,
)
from backend.utils.time import utc_now


class ReadinessStatus(BaseModel):
    """Shape of the readiness probe response."""

    ready: bool
    profile: str
    stages: list[StartupStageResult] = Field(default_factory=list)
    checked_at: str


class ReadinessService:
    """Reports readiness from the StartupManager's own last recorded run."""

    def __init__(self, startup_manager: StartupManager) -> None:
        self._startup_manager = startup_manager

    def check(self) -> ReadinessStatus:
        report = self._startup_manager.last_report
        if report is None:
            return ReadinessStatus(ready=False, profile="unknown", stages=[], checked_at=utc_now().isoformat())
        return ReadinessStatus(
            ready=report.completed, profile=report.profile, stages=report.stages, checked_at=utc_now().isoformat()
        )
