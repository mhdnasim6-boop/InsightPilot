"""Request models for /api/v1/distributed.

Mirrors every other phase's own ``backend/schemas/*_request.py`` module —
REST-only shapes, distinct from the distributed domain's own
``backend/distributed/models/``.
"""

from typing import Any

from pydantic import BaseModel, Field


class RegisterWorkerRequest(BaseModel):
    """Body for POST /distributed/workers/register."""

    worker_id: str
    hostname: str
    capabilities: list[str] = Field(default_factory=list)
    maximum_parallel_tasks: int = Field(default=1, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerHeartbeatRequest(BaseModel):
    """Body for POST /distributed/workers/heartbeat."""

    worker_id: str
    active_task_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkerActionRequest(BaseModel):
    """Body for POST /distributed/workers/drain and .../shutdown."""

    worker_id: str
