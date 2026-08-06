"""WorkloadRouter: the schedule -> failover-check -> dispatch -> allocate sequence.

Composes ``FederationScheduler``/``FailoverManager``/``ClusterAllocator``
into the one call sequence ``FederationCoordinator`` needs — kept
separate from the coordinator itself so this sequencing logic is
testable without a real ``WorkflowService`` in the picture.
"""

from backend.federation.coordination.cluster_allocator import ClusterAllocator
from backend.federation.models.remote_execution import RemoteExecution
from backend.federation.models.routing_decision import RoutingDecision
from backend.federation.scheduler.failover_manager import FailoverManager
from backend.federation.scheduler.federation_scheduler import FederationScheduler


class WorkloadRouter:
    """Routes one workload to a cluster and opens its RemoteExecution credit."""

    def __init__(
        self, federation_scheduler: FederationScheduler, failover_manager: FailoverManager, cluster_allocator: ClusterAllocator,
    ) -> None:
        self._federation_scheduler = federation_scheduler
        self._failover_manager = failover_manager
        self._cluster_allocator = cluster_allocator

    def route(
        self, workflow_id: str, required_agents: list[str], step_count: int, plan_id: str | None = None,
    ) -> tuple[RoutingDecision, RemoteExecution]:
        """Schedule, failover-check, dispatch, and allocate — the full pre-execution sequence."""
        decision = self._federation_scheduler.schedule(workflow_id, required_agents, step_count, plan_id)
        decision = self._failover_manager.check_and_reroute(decision.decision_id)
        decision = self._federation_scheduler.mark_dispatched(decision.decision_id)
        remote_execution = self._cluster_allocator.allocate(decision)
        return decision, remote_execution

    def finish(self, decision_id: str, remote_execution_id: str, success: bool, error: str | None = None) -> None:
        """Close out both the RemoteExecution credit and the RoutingDecision it came from."""
        self._cluster_allocator.release(remote_execution_id, success, error)
        if success:
            self._federation_scheduler.complete(decision_id)
        else:
            self._federation_scheduler.fail(decision_id, error or "unknown error")
