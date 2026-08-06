"""Background job manager provider."""

from functools import lru_cache

from backend.core.job_manager import JobManager


@lru_cache
def get_job_manager() -> JobManager:
    """Return the process-wide job manager singleton."""
    return JobManager()
