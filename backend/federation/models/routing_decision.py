"""RoutingDecision: which cluster a workload is credited to, and why.

The scheduling verdict itself — mirrors `TaskAssignment`'s own role in
Phase 38, one layer up (cluster-level credit instead of worker-level
credit). Stays PENDING (reroutable by `FailoverManager`) until
``mark_dispatched()`` — "work that has not yet begun execution" is
exactly "a decision still in PENDING." Once DISPATCHED, a decision is
never rerouted again: "already-running work remains owned by its
original cluster."
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RoutingDecisionStatus(str, Enum):
    """Lifecycle of one RoutingDecision.

    There is deliberately no separate ``REROUTED`` member: a reroute
    (``FederationScheduler.reroute()``) redirects ``selected_cluster_id``
    but leaves the decision PENDING (it's still awaiting dispatch, just
    to a new cluster now) — ``reroute_count`` is what makes a reroute
    observable, not a transient status value.
    """

    PENDING = "pending"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"


class RoutingDecision(BaseModel):
    """One scheduling verdict: which cluster a workflow's execution is credited to."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    workflow_id: str
    plan_id: str | None = None
    required_agents: list[str] = Field(default_factory=list)
    step_count: int = 0
    candidate_cluster_ids: list[str] = Field(default_factory=list)
    selected_cluster_id: str
    reason: str
    status: RoutingDecisionStatus = RoutingDecisionStatus.PENDING
    decided_at: datetime
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    reroute_count: int = 0
