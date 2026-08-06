"""FailoverManager: reroutes still-PENDING RoutingDecisions off a cluster
that's no longer available.

"If a destination cluster becomes unavailable, reroute only work that
has not yet begun execution. Already-running work remains owned by its
original cluster" — made concrete literally: a decision is only ever
touched here while it is still PENDING (before
``FederationScheduler.mark_dispatched()``); once DISPATCHED, this class
never looks at it again. Mirrors
``backend.distributed.recovery.task_recovery.TaskRecovery``'s own
narrow, single-responsibility shape (Phase 38) one layer up.
"""

from backend.federation.exceptions import NoEligibleClusterError
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.models.routing_decision import (
    RoutingDecision,
    RoutingDecisionStatus,
)
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.federation.scheduler.federation_scheduler import FederationScheduler

_UNAVAILABLE_STATUSES = frozenset({ClusterStatus.OFFLINE, ClusterStatus.FAILED, ClusterStatus.MAINTENANCE})


class FailoverManager:
    """Reroutes PENDING decisions whose target cluster has become unavailable."""

    def __init__(
        self, federation_scheduler: FederationScheduler, cluster_selector: ClusterSelector, cluster_registry: ClusterRegistry,
    ) -> None:
        self._federation_scheduler = federation_scheduler
        self._cluster_selector = cluster_selector
        self._cluster_registry = cluster_registry

    def check_and_reroute(self, decision_id: str) -> RoutingDecision:
        """Reroute ``decision_id`` if it is still PENDING and its cluster is unavailable.
        A no-op (returns the decision unchanged) otherwise."""
        decision = self._federation_scheduler.get(decision_id)
        if decision.status != RoutingDecisionStatus.PENDING:
            return decision

        cluster = self._cluster_registry.get(decision.selected_cluster_id)
        if cluster.status not in _UNAVAILABLE_STATUSES and cluster.has_capacity():
            return decision

        already_tried = set(decision.candidate_cluster_ids)
        replacement = self._cluster_selector.select_for(decision.required_agents, decision.step_count, exclude=already_tried)
        if replacement is None:
            raise NoEligibleClusterError(
                f"Cluster '{decision.selected_cluster_id}' is unavailable and no other "
                f"cluster can serve workflow '{decision.workflow_id}'."
            )
        return self._federation_scheduler.reroute(
            decision_id, replacement.cluster_id,
            reason=f"rerouted from unavailable cluster '{cluster.cluster_id}' ({cluster.status.value})",
        )

    def sweep_pending(self) -> list[RoutingDecision]:
        """Check every currently PENDING decision, rerouting any whose cluster is unavailable."""
        return [self.check_and_reroute(decision.decision_id) for decision in self._federation_scheduler.list_pending()]
