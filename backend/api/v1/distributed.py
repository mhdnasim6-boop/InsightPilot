"""Distributed execution endpoints: worker registration/heartbeat/drain/shutdown,
cluster statistics, and the task queue snapshot — thin wrappers over
``DistributedExecutionService``, exactly like every other router in this codebase.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.distributed import get_distributed_execution_service
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.models.worker import Worker
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.schemas.distributed_request import (
    RegisterWorkerRequest,
    WorkerActionRequest,
    WorkerHeartbeatRequest,
)
from backend.schemas.response import SuccessResponse
from backend.security.authorization.permission import Permission
from backend.security.middleware.authorization import require_permission
from backend.security.models.authenticated_user import AuthenticatedUser

router = APIRouter(prefix="/distributed")


@router.get("/workers", response_model=SuccessResponse[list[Worker]], summary="List every registered worker")
async def list_workers(
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[Worker]]:
    """Every registered worker, after a staleness sweep."""
    return SuccessResponse.ok(data=service.list_workers(), message="Workers fetched.")


@router.post("/workers/register", response_model=SuccessResponse[Worker], summary="Register a worker")
async def register_worker(
    body: RegisterWorkerRequest,
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_SYSTEM)),
) -> SuccessResponse[Worker]:
    """Register (or re-register) a worker. Idempotent by worker_id."""
    worker = service.register_worker(
        body.worker_id, body.hostname, body.capabilities, body.maximum_parallel_tasks, body.metadata
    )
    return SuccessResponse.ok(data=worker, message=f"Worker '{worker.worker_id}' registered.")


@router.post("/workers/heartbeat", response_model=SuccessResponse[Worker], summary="Record a worker heartbeat")
async def worker_heartbeat(
    body: WorkerHeartbeatRequest,
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_SYSTEM)),
) -> SuccessResponse[Worker]:
    """Record a heartbeat — renews the worker's leases and revives it if it was OFFLINE."""
    worker = service.heartbeat(body.worker_id, body.active_task_count, body.metadata)
    return SuccessResponse.ok(data=worker, message="Heartbeat recorded.")


@router.post("/workers/drain", response_model=SuccessResponse[Worker], summary="Drain a worker")
async def drain_worker(
    body: WorkerActionRequest,
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_SYSTEM)),
) -> SuccessResponse[Worker]:
    """Stop routing new work to a worker; its existing tasks run to completion."""
    return SuccessResponse.ok(data=service.drain_worker(body.worker_id), message="Worker draining.")


@router.post("/workers/shutdown", response_model=SuccessResponse[Worker], summary="Shut down a worker")
async def shutdown_worker(
    body: WorkerActionRequest,
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_SYSTEM)),
) -> SuccessResponse[Worker]:
    """Gracefully take a worker offline: reclaim its outstanding work first, then mark it OFFLINE."""
    return SuccessResponse.ok(data=service.shutdown_worker(body.worker_id), message="Worker shut down.")


@router.get("/cluster", response_model=SuccessResponse[ClusterStatistics], summary="Cluster statistics")
async def get_cluster_statistics(
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[ClusterStatistics]:
    """Aggregate counts across the whole worker fleet."""
    return SuccessResponse.ok(data=service.cluster_statistics(), message="Cluster statistics fetched.")


@router.get("/queue", response_model=SuccessResponse[dict[str, list[TaskAssignment]]], summary="Task queue snapshot")
async def get_queue_snapshot(
    service: DistributedExecutionService = Depends(get_distributed_execution_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[dict[str, list[TaskAssignment]]]:
    """Every currently active and retry-pending task assignment."""
    return SuccessResponse.ok(data=service.queue_snapshot(), message="Queue snapshot fetched.")
