"""FederationScheduler: owns every RoutingDecision's lifecycle.

This is the one piece of "scheduling" this phase adds, and it is
deliberately narrow — it never runs a workflow itself
(``WorkflowService``/``ExecutionService`` already do that, unchanged, in
``FederationCoordinator``) — it only records *which cluster a workload is
credited to* and tracks that decision through PENDING -> DISPATCHED ->
COMPLETED/FAILED (or PENDING -> REROUTED, via ``reroute()``, called by
``FailoverManager``). Raises ``NoEligibleClusterError`` if nothing can
serve a workload at all — unlike Phase 38's ``DispatchScheduler``
(silently returns ``None``, a no-op is meaningful there since a step can
always still run locally with zero workers registered), federation
always has *at least* the local cluster registered
(``FederationService`` seeds it), so "no eligible cluster" only happens
if the workload's own requirements are impossible to satisfy anywhere —
a genuine, reportable error, not a normal "no workers yet" case.
"""

from backend.federation.exceptions import (
    NoEligibleClusterError,
    RoutingDecisionNotFoundError,
)
from backend.federation.models.routing_decision import (
    RoutingDecision,
    RoutingDecisionStatus,
)
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class FederationScheduler:
    """Creates RoutingDecisions and tracks each one's lifecycle."""

    def __init__(self, cluster_selector: ClusterSelector) -> None:
        self._cluster_selector = cluster_selector
        self._decisions: dict[str, RoutingDecision] = {}

    def schedule(self, workflow_id: str, required_agents: list[str], step_count: int, plan_id: str | None = None) -> RoutingDecision:
        """Create a PENDING RoutingDecision for a workflow. Raises NoEligibleClusterError
        if no registered cluster (including the local one) can serve it."""
        cluster = self._cluster_selector.select_for(required_agents, step_count)
        if cluster is None:
            raise NoEligibleClusterError(
                f"No registered cluster can serve workflow '{workflow_id}' "
                f"(requires agents {required_agents}, {step_count} step(s))."
            )
        decision = RoutingDecision(
            decision_id=generate_id(), workflow_id=workflow_id, plan_id=plan_id,
            required_agents=required_agents, step_count=step_count,
            candidate_cluster_ids=[cluster.cluster_id], selected_cluster_id=cluster.cluster_id,
            reason=f"least-loaded eligible cluster (load_ratio={cluster.load_ratio():.2f})",
            decided_at=utc_now(),
        )
        self._decisions[decision.decision_id] = decision
        return decision

    def get(self, decision_id: str) -> RoutingDecision:
        """Fetch a routing decision. Raises RoutingDecisionNotFoundError if unknown."""
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise RoutingDecisionNotFoundError(f"No routing decision found for '{decision_id}'.")
        return decision

    def reroute(self, decision_id: str, new_cluster_id: str, reason: str) -> RoutingDecision:
        """Redirect a still-PENDING decision to a different cluster. Called only by FailoverManager."""
        decision = self.get(decision_id)
        rerouted = decision.model_copy(
            update={
                "selected_cluster_id": new_cluster_id,
                "candidate_cluster_ids": [*decision.candidate_cluster_ids, new_cluster_id],
                "status": RoutingDecisionStatus.PENDING,
                "reason": reason,
                "reroute_count": decision.reroute_count + 1,
            }
        )
        self._decisions[decision_id] = rerouted
        return rerouted

    def mark_dispatched(self, decision_id: str) -> RoutingDecision:
        """Mark a decision DISPATCHED — the point of no return; never rerouted again afterward."""
        decision = self.get(decision_id)
        dispatched = decision.model_copy(update={"status": RoutingDecisionStatus.DISPATCHED, "dispatched_at": utc_now()})
        self._decisions[decision_id] = dispatched
        return dispatched

    def complete(self, decision_id: str) -> RoutingDecision:
        """Mark a decision COMPLETED."""
        return self._finish(decision_id, RoutingDecisionStatus.COMPLETED, error=None)

    def fail(self, decision_id: str, error: str) -> RoutingDecision:
        """Mark a decision FAILED."""
        return self._finish(decision_id, RoutingDecisionStatus.FAILED, error=error)

    def _finish(self, decision_id: str, status: RoutingDecisionStatus, error: str | None) -> RoutingDecision:
        decision = self.get(decision_id)
        finished = decision.model_copy(update={"status": status, "completed_at": utc_now(), "error": error})
        self._decisions[decision_id] = finished
        return finished

    def list_pending(self) -> list[RoutingDecision]:
        """Every currently PENDING routing decision — what FailoverManager sweeps."""
        return [d for d in self._decisions.values() if d.status == RoutingDecisionStatus.PENDING]

    def list_all(self) -> list[RoutingDecision]:
        """Every routing decision ever created, in creation order."""
        return list(self._decisions.values())
