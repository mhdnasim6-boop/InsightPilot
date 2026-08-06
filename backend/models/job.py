"""Background job domain model."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobStatus(str, Enum):
    """Lifecycle states of a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    """A unit of background work tracked entirely in memory by JobManager."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str
    name: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any | None = None
    error: str | None = None
