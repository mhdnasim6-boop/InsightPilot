"""Lease: exclusive, time-bounded ownership of one TaskAssignment by one worker.

A lease is what makes recovery honest: if a worker goes silent
mid-task, its lease eventually expires (rather than the task being
considered "owned forever"), and ``TaskRecovery`` can safely reclaim it.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Lease(BaseModel):
    """One worker's exclusive, expiring claim on one TaskAssignment."""

    model_config = ConfigDict(frozen=True)

    lease_id: str
    assignment_id: str
    worker_id: str
    granted_at: datetime
    expires_at: datetime
    renewed_count: int = 0

    def is_expired(self, now: datetime) -> bool:
        """Whether this lease's expiry has already passed as of ``now``."""
        return now >= self.expires_at
