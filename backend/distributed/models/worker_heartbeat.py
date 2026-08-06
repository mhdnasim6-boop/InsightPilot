"""WorkerHeartbeat: one received heartbeat, kept for latency/history reporting.

``HeartbeatManager`` keeps only a short, bounded history per worker (see
its own docstring) — this model is the one entry in that history, not a
second source of truth for "is this worker alive" (``Worker.last_heartbeat``
is that source).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkerHeartbeat(BaseModel):
    """One heartbeat received from a worker."""

    model_config = ConfigDict(frozen=True)

    heartbeat_id: str
    worker_id: str
    received_at: datetime
    active_task_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
