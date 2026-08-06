"""ClusterAllocator: credits/releases cluster capacity and owns RemoteExecution records.

Mirrors ``backend.distributed.registry.worker_registry.WorkerRegistry``'s
own ``add_active_task``/``remove_active_task`` role (Phase 38) one layer
up — a cluster's ``active_remote_executions`` is exactly the capacity
signal ``RoutingEngine``/``Cluster.has_capacity()`` read, so allocating
here is what makes load-aware routing correct for the *next* workload.
"""

from backend.federation.models.remote_execution import (
    RemoteExecution,
    RemoteExecutionStatus,
)
from backend.federation.models.routing_decision import RoutingDecision
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class ClusterAllocator:
    """Creates RemoteExecution records and keeps each cluster's active-execution credit accurate."""

    def __init__(self, cluster_registry: ClusterRegistry) -> None:
        self._cluster_registry = cluster_registry
        self._executions: dict[str, RemoteExecution] = {}

    def allocate(self, decision: RoutingDecision) -> RemoteExecution:
        """Credit the decision's selected cluster and open a new RemoteExecution for it."""
        remote_execution = RemoteExecution(
            remote_execution_id=generate_id(), decision_id=decision.decision_id,
            cluster_id=decision.selected_cluster_id, workflow_id=decision.workflow_id,
            plan_id=decision.plan_id, started_at=utc_now(),
        )
        self._executions[remote_execution.remote_execution_id] = remote_execution
        self._cluster_registry.add_active_execution(decision.selected_cluster_id, remote_execution.remote_execution_id)
        return remote_execution

    def release(self, remote_execution_id: str, success: bool, error: str | None = None) -> RemoteExecution:
        """Close out a RemoteExecution and release its cluster's capacity credit."""
        remote_execution = self._executions[remote_execution_id]
        status = RemoteExecutionStatus.COMPLETED if success else RemoteExecutionStatus.FAILED
        finished = remote_execution.model_copy(update={"status": status, "completed_at": utc_now(), "error": error})
        self._executions[remote_execution_id] = finished
        self._cluster_registry.remove_active_execution(remote_execution.cluster_id, remote_execution_id)
        return finished

    def get(self, remote_execution_id: str) -> RemoteExecution:
        """Fetch a RemoteExecution by id."""
        return self._executions[remote_execution_id]

    def list_all(self) -> list[RemoteExecution]:
        """Every RemoteExecution ever created, in creation order."""
        return list(self._executions.values())

    def list_for_cluster(self, cluster_id: str) -> list[RemoteExecution]:
        """Every RemoteExecution ever credited to ``cluster_id``."""
        return [execution for execution in self._executions.values() if execution.cluster_id == cluster_id]
