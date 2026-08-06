"""Distributed execution providers: registry, scheduler, queues, heartbeat,
recovery, and the top-level DistributedExecutionService.

Caching mirrors this package's own established convention exactly: the
genuinely stateful collaborators (``WorkerRegistry``, ``LeaseManager``,
``TaskQueue``, ``RetryQueue``, ``HeartbeatManager``, ``WorkerMonitor``)
are ``@lru_cache``'d process-wide singletons — a worker registered in one
request must still be there in the next. Every stateless composition on
top (``LoadBalancer``, ``WorkerSelector``, ``DispatchScheduler``,
``TaskRecovery``, ``WorkerRecovery``, ``DistributedCapabilityRegistry``,
and ``DistributedExecutionService`` itself) is left uncached, mirroring
``get_execution_service``/``get_workflow_service``: cheap to rebuild, and
every piece of state that must survive across requests already lives in
the cached collaborators these functions are handed.
"""

from functools import lru_cache

from fastapi import Depends

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.dependencies.execution_checkpoint import get_execution_checkpoint_store
from backend.dependencies.orchestration import get_capability_registry
from backend.distributed.heartbeat.heartbeat_manager import HeartbeatManager
from backend.distributed.heartbeat.worker_monitor import WorkerMonitor
from backend.distributed.queue.retry_queue import RetryQueue
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.recovery.task_recovery import TaskRecovery
from backend.distributed.recovery.worker_recovery import WorkerRecovery
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.dispatch_scheduler import DispatchScheduler
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.distributed.scheduler.load_balancer import LoadBalancer
from backend.distributed.scheduler.worker_selector import WorkerSelector
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore


@lru_cache
def get_worker_registry() -> WorkerRegistry:
    """Return the process-wide WorkerRegistry singleton — every registered worker lives here."""
    return WorkerRegistry()


@lru_cache
def get_lease_manager() -> LeaseManager:
    """Return the process-wide LeaseManager singleton."""
    return LeaseManager()


@lru_cache
def get_task_queue() -> TaskQueue:
    """Return the process-wide TaskQueue singleton — every active assignment lives here."""
    return TaskQueue()


@lru_cache
def get_retry_queue() -> RetryQueue:
    """Return the process-wide RetryQueue singleton."""
    return RetryQueue()


@lru_cache
def get_heartbeat_manager(
    worker_registry: WorkerRegistry = Depends(get_worker_registry),
    lease_manager: LeaseManager = Depends(get_lease_manager),
) -> HeartbeatManager:
    """Return the process-wide HeartbeatManager singleton — keeps each worker's heartbeat history."""
    return HeartbeatManager(worker_registry, lease_manager)


@lru_cache
def get_worker_monitor(worker_registry: WorkerRegistry = Depends(get_worker_registry)) -> WorkerMonitor:
    """Return the process-wide WorkerMonitor singleton."""
    return WorkerMonitor(worker_registry)


@lru_cache
def get_load_balancer() -> LoadBalancer:
    """Return the process-wide LoadBalancer singleton. Stateless — cached only for identity reuse."""
    return LoadBalancer()


def get_distributed_capability_registry(
    agent_capability_registry: AgentCapabilityRegistry = Depends(get_capability_registry),
) -> DistributedCapabilityRegistry:
    """Provide a DistributedCapabilityRegistry backed by the real, live AgentCapabilityRegistry."""
    return DistributedCapabilityRegistry(agent_capability_registry)


def get_worker_selector(
    worker_registry: WorkerRegistry = Depends(get_worker_registry),
    capability_registry: DistributedCapabilityRegistry = Depends(get_distributed_capability_registry),
    load_balancer: LoadBalancer = Depends(get_load_balancer),
) -> WorkerSelector:
    """Provide a WorkerSelector wired to the shared, process-wide registries."""
    return WorkerSelector(worker_registry, capability_registry, load_balancer)


def get_dispatch_scheduler(
    worker_selector: WorkerSelector = Depends(get_worker_selector),
    worker_registry: WorkerRegistry = Depends(get_worker_registry),
    lease_manager: LeaseManager = Depends(get_lease_manager),
    task_queue: TaskQueue = Depends(get_task_queue),
) -> DispatchScheduler:
    """Provide a DispatchScheduler wired to the shared, process-wide collaborators."""
    return DispatchScheduler(worker_selector, worker_registry, lease_manager, task_queue)


def get_task_recovery(
    task_queue: TaskQueue = Depends(get_task_queue),
    retry_queue: RetryQueue = Depends(get_retry_queue),
    lease_manager: LeaseManager = Depends(get_lease_manager),
    worker_registry: WorkerRegistry = Depends(get_worker_registry),
    checkpoint_store: ExecutionCheckpointStore = Depends(get_execution_checkpoint_store),
) -> TaskRecovery:
    """Provide a TaskRecovery wired to the shared, process-wide collaborators + the real ExecutionCheckpointStore."""
    return TaskRecovery(task_queue, retry_queue, lease_manager, worker_registry, checkpoint_store)


def get_worker_recovery(
    task_queue: TaskQueue = Depends(get_task_queue),
    task_recovery: TaskRecovery = Depends(get_task_recovery),
) -> WorkerRecovery:
    """Provide a WorkerRecovery wired to the shared, process-wide TaskQueue/TaskRecovery."""
    return WorkerRecovery(task_queue, task_recovery)


def get_distributed_execution_service(
    worker_registry: WorkerRegistry = Depends(get_worker_registry),
    capability_registry: DistributedCapabilityRegistry = Depends(get_distributed_capability_registry),
    dispatch_scheduler: DispatchScheduler = Depends(get_dispatch_scheduler),
    task_queue: TaskQueue = Depends(get_task_queue),
    retry_queue: RetryQueue = Depends(get_retry_queue),
    heartbeat_manager: HeartbeatManager = Depends(get_heartbeat_manager),
    worker_monitor: WorkerMonitor = Depends(get_worker_monitor),
    worker_recovery: WorkerRecovery = Depends(get_worker_recovery),
) -> DistributedExecutionService:
    """Provide the DistributedExecutionService — the only object anything should use for
    worker registration, dispatch, heartbeats, and recovery.

    Deliberately uncached, mirroring ``get_execution_service``/``get_workflow_service``:
    every piece of state that must survive across requests already lives
    in the cached ``WorkerRegistry``/``LeaseManager``/``TaskQueue``/
    ``RetryQueue``/``HeartbeatManager``/``WorkerMonitor`` this function's
    own dependencies are built from.
    """
    return DistributedExecutionService(
        worker_registry, capability_registry, dispatch_scheduler, task_queue, retry_queue,
        heartbeat_manager, worker_monitor, worker_recovery,
    )
