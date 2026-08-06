"""Tests for the in-memory background job manager."""

import asyncio

from backend.core.job_manager import JobManager
from backend.models.job import JobStatus


def test_job_completes_successfully() -> None:
    async def scenario() -> None:
        manager = JobManager()

        async def work() -> str:
            return "done"

        job = manager.submit("demo", work)
        assert job.status in (JobStatus.PENDING, JobStatus.RUNNING)

        await asyncio.sleep(0.05)

        finished = manager.get(job.job_id)
        assert finished is not None
        assert finished.status == JobStatus.COMPLETED
        assert finished.result == "done"

    asyncio.run(scenario())


def test_job_records_failure() -> None:
    async def scenario() -> None:
        manager = JobManager()

        async def failing_work() -> None:
            raise RuntimeError("boom")

        job = manager.submit("demo-fail", failing_work)
        await asyncio.sleep(0.05)

        finished = manager.get(job.job_id)
        assert finished is not None
        assert finished.status == JobStatus.FAILED
        assert finished.error == "boom"

    asyncio.run(scenario())


def test_job_manager_lists_all_jobs() -> None:
    async def scenario() -> None:
        manager = JobManager()

        async def work() -> None:
            return None

        job_one = manager.submit("one", work)
        job_two = manager.submit("two", work)
        await asyncio.sleep(0.05)

        job_ids = {job.job_id for job in manager.list()}
        assert job_ids == {job_one.job_id, job_two.job_id}

    asyncio.run(scenario())
