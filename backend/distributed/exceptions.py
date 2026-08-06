"""Distributed layer exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module.
"""

from backend.core.exceptions import InsightPilotError


class DistributedError(InsightPilotError):
    """Base class for every distributed-layer exception."""

    status_code = 500
    error_type = "DistributedError"


class WorkerNotFoundError(DistributedError):
    """Raised when a worker is looked up by an unregistered worker_id."""

    status_code = 404
    error_type = "WorkerNotFoundError"


class WorkerAlreadyRegisteredError(DistributedError):
    """Raised when registering a worker_id that is already active."""

    status_code = 409
    error_type = "WorkerAlreadyRegisteredError"


class InvalidWorkerStateError(DistributedError):
    """Raised when a requested transition doesn't make sense for a worker's current status."""

    status_code = 422
    error_type = "InvalidWorkerStateError"


class LeaseNotFoundError(DistributedError):
    """Raised when a lease is looked up by an unknown lease_id."""

    status_code = 404
    error_type = "LeaseNotFoundError"


class TaskAssignmentNotFoundError(DistributedError):
    """Raised when a task assignment is looked up by an unknown assignment_id."""

    status_code = 404
    error_type = "TaskAssignmentNotFoundError"
