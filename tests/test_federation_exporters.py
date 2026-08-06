"""Tests for backend.federation.exporters: JSON and Mermaid federation exports."""

import json

from backend.federation.exporters.json_exporter import export_federation_json
from backend.federation.exporters.mermaid_exporter import export_federation_mermaid
from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.federation_statistics import FederationStatistics
from backend.federation.models.routing_decision import RoutingDecision
from backend.utils.time import utc_now


def _cluster() -> Cluster:
    return Cluster(
        cluster_id="c1", name="Cluster One", endpoint="https://c1.example.com",
        capabilities=ClusterCapability(maximum_concurrent_executions=2), active_remote_executions=["r1"],
    )


def _decision() -> RoutingDecision:
    return RoutingDecision(
        decision_id="d1", workflow_id="wf1", selected_cluster_id="c1", reason="least loaded", decided_at=utc_now(),
    )


def test_export_federation_json_round_trips() -> None:
    payload = export_federation_json([_cluster()], [_decision()], FederationStatistics(generated_at=utc_now()))
    parsed = json.loads(payload)
    assert parsed["clusters"][0]["cluster_id"] == "c1"
    assert parsed["routing_decisions"][0]["decision_id"] == "d1"
    assert "statistics" in parsed


def test_export_federation_mermaid_includes_cluster_and_workflow() -> None:
    mermaid = export_federation_mermaid([_cluster()], [_decision()])
    assert "flowchart LR" in mermaid
    assert "c1" in mermaid
    assert "wf1" in mermaid
