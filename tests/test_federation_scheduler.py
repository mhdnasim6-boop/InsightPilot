"""Tests for backend.federation.scheduler: RoutingEngine, ClusterSelector,
FederationScheduler, and FailoverManager.
"""

import pytest

from backend.federation.exceptions import (
    NoEligibleClusterError,
    RoutingDecisionNotFoundError,
)
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.models.routing_decision import RoutingDecisionStatus
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.registry.federation_directory import FederationDirectory
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.federation.scheduler.failover_manager import FailoverManager
from backend.federation.scheduler.federation_scheduler import FederationScheduler
from backend.federation.scheduler.routing_engine import RoutingEngine


def _capabilities(**overrides: object) -> ClusterCapability:
    defaults: dict[str, object] = {"supported_agents": ["browser_agent"], "maximum_concurrent_executions": 2}
    defaults.update(overrides)
    return ClusterCapability(**defaults)  # type: ignore[arg-type]


def _selector(registry: ClusterRegistry) -> ClusterSelector:
    return ClusterSelector(FederationDirectory(registry), RoutingEngine())


# -- RoutingEngine ------------------------------------------------------------------------


def test_routing_engine_returns_none_for_empty_candidates() -> None:
    assert RoutingEngine().select([]) is None


def test_routing_engine_picks_least_loaded() -> None:
    registry = ClusterRegistry()
    registry.register("busy", "Busy", "https://busy.example.com", _capabilities())
    registry.add_active_execution("busy", "r1")
    registry.register("idle", "Idle", "https://idle.example.com", _capabilities())

    selected = RoutingEngine().select(registry.list_all())

    assert selected is not None
    assert selected.cluster_id == "idle"


# -- ClusterSelector ------------------------------------------------------------------------


def test_cluster_selector_returns_none_with_no_clusters() -> None:
    assert _selector(ClusterRegistry()).select_for(["browser_agent"], 1) is None


def test_cluster_selector_excludes_given_cluster_ids() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    registry.register("c2", "Two", "https://c2.example.com", _capabilities())

    selected = _selector(registry).select_for(["browser_agent"], 1, exclude={"c1"})

    assert selected is not None
    assert selected.cluster_id == "c2"


# -- FederationScheduler ----------------------------------------------------------------------


def test_schedule_raises_when_nothing_eligible() -> None:
    scheduler = FederationScheduler(_selector(ClusterRegistry()))
    with pytest.raises(NoEligibleClusterError):
        scheduler.schedule("wf1", ["browser_agent"], 1)


def test_schedule_creates_a_pending_decision() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    scheduler = FederationScheduler(_selector(registry))

    decision = scheduler.schedule("wf1", ["browser_agent"], 3, plan_id="p1")

    assert decision.status == RoutingDecisionStatus.PENDING
    assert decision.selected_cluster_id == "c1"
    assert decision.required_agents == ["browser_agent"]
    assert decision.step_count == 3
    assert decision.plan_id == "p1"


def test_get_raises_for_unknown_decision() -> None:
    scheduler = FederationScheduler(_selector(ClusterRegistry()))
    with pytest.raises(RoutingDecisionNotFoundError):
        scheduler.get("does-not-exist")


def test_mark_dispatched_then_complete() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    scheduler = FederationScheduler(_selector(registry))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)

    dispatched = scheduler.mark_dispatched(decision.decision_id)
    assert dispatched.status == RoutingDecisionStatus.DISPATCHED
    assert dispatched.dispatched_at is not None

    completed = scheduler.complete(decision.decision_id)
    assert completed.status == RoutingDecisionStatus.COMPLETED


def test_fail_records_error() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    scheduler = FederationScheduler(_selector(registry))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)

    failed = scheduler.fail(decision.decision_id, "boom")

    assert failed.status == RoutingDecisionStatus.FAILED
    assert failed.error == "boom"


def test_reroute_updates_selected_cluster_and_increments_count() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    scheduler = FederationScheduler(_selector(registry))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)

    rerouted = scheduler.reroute(decision.decision_id, "c2", reason="c1 went offline")

    assert rerouted.selected_cluster_id == "c2"
    assert rerouted.reroute_count == 1
    assert rerouted.status == RoutingDecisionStatus.PENDING


def test_list_pending_and_list_all() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    scheduler = FederationScheduler(_selector(registry))
    d1 = scheduler.schedule("wf1", ["browser_agent"], 1)
    scheduler.schedule("wf2", ["browser_agent"], 1)
    scheduler.mark_dispatched(d1.decision_id)

    assert len(scheduler.list_all()) == 2
    assert [d.workflow_id for d in scheduler.list_pending()] == ["wf2"]


# -- FailoverManager ------------------------------------------------------------------------


def test_failover_leaves_pending_decision_alone_when_cluster_still_available() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    selector = _selector(registry)
    scheduler = FederationScheduler(selector)
    failover = FailoverManager(scheduler, selector, registry)
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)

    unchanged = failover.check_and_reroute(decision.decision_id)

    assert unchanged.selected_cluster_id == "c1"
    assert unchanged.reroute_count == 0


def test_failover_reroutes_pending_decision_off_an_unavailable_cluster() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    registry.register("c2", "Two", "https://c2.example.com", _capabilities())
    selector = _selector(registry)
    scheduler = FederationScheduler(selector)
    failover = FailoverManager(scheduler, selector, registry)
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    assert decision.selected_cluster_id in {"c1", "c2"}
    registry.set_status(decision.selected_cluster_id, ClusterStatus.OFFLINE)

    rerouted = failover.check_and_reroute(decision.decision_id)

    assert rerouted.selected_cluster_id != decision.selected_cluster_id
    assert rerouted.reroute_count == 1
    assert rerouted.status == RoutingDecisionStatus.PENDING


def test_failover_never_touches_a_dispatched_decision() -> None:
    """'Already-running work remains owned by its original cluster.'"""
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    selector = _selector(registry)
    scheduler = FederationScheduler(selector)
    failover = FailoverManager(scheduler, selector, registry)
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    scheduler.mark_dispatched(decision.decision_id)
    registry.set_status("c1", ClusterStatus.OFFLINE)

    unchanged = failover.check_and_reroute(decision.decision_id)

    assert unchanged.selected_cluster_id == "c1"
    assert unchanged.status == RoutingDecisionStatus.DISPATCHED
    assert unchanged.reroute_count == 0


def test_failover_raises_when_no_replacement_exists() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    selector = _selector(registry)
    scheduler = FederationScheduler(selector)
    failover = FailoverManager(scheduler, selector, registry)
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    registry.set_status("c1", ClusterStatus.OFFLINE)

    with pytest.raises(NoEligibleClusterError):
        failover.check_and_reroute(decision.decision_id)


def test_sweep_pending_reroutes_every_affected_decision() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    registry.register("c2", "Two", "https://c2.example.com", _capabilities())
    selector = _selector(registry)
    scheduler = FederationScheduler(selector)
    failover = FailoverManager(scheduler, selector, registry)
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    registry.set_status(decision.selected_cluster_id, ClusterStatus.OFFLINE)

    results = failover.sweep_pending()

    assert len(results) == 1
    assert results[0].reroute_count == 1
