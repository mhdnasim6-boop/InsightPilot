"""In-memory background job framework.

No Celery, no Redis — jobs run as ``asyncio`` tasks within the same
process. This is intentionally minimal: it exists so future long-running
work (dataset analysis, report generation, agent runs) has somewhere to
register and report progress, without committing to a task-queue
technology yet. Unlike sessions/files, jobs have no stated requirement to
survive a process restart, so there's no repository abstraction here —
JobManager owns its in-memory state directly.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from backend.models.job import Job, JobStatus
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

JobFactory = Callable[[], Awaitable[Any]]


class JobManager:
    """Tracks and runs background jobs in memory for the life of the process."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def submit(self, name: str, coro_factory: JobFactory) -> Job:
        """Register a job and schedule it to run in the background immediately."""
        job = Job(job_id=generate_id(), name=name, status=JobStatus.PENDING, created_at=utc_now())
        self._jobs[job.job_id] = job
        self._tasks[job.job_id] = asyncio.create_task(self._run(job.job_id, coro_factory))
        return job

    async def _run(self, job_id: str, coro_factory: JobFactory) -> None:
        job = self._jobs[job_id]
        job.status = JobStatus.RUNNING
        job.started_at = utc_now()
        try:
            job.result = await coro_factory()
            job.status = JobStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001 - intentionally broad: a job's own failure must not crash the manager
            job.status = JobStatus.FAILED
            job.error = str(exc)
            logger.exception("Job '{}' ({}) failed", job_id, job.name)
        finally:
            job.completed_at = utc_now()

    def get(self, job_id: str) -> Job | None:
        """Return a job by ID, or None if it doesn't exist."""
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        """Return all tracked jobs."""
        return list(self._jobs.values())
