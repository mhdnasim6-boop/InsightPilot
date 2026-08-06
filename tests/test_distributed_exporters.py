"""Tests for backend.distributed.exporters: JSON and Mermaid cluster exports."""

import json

from backend.distributed.exporters.json_exporter import export_cluster_json
from backend.distributed.exporters.mermaid_exporter import export_cluster_mermaid
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_capability import WorkerCapability
from backend.utils.time import utc_now


def _worker() -> Worker:
    return Worker(
        worker_id="w1", hostname="host-1", capabilities=[WorkerCapability(node_name="browser_agent")],
        maximum_parallel_tasks=2, active_tasks=["a1"],
    )


def _assignment() -> TaskAssignment:
    return TaskAssignment(
        assignment_id="a1", step_id="s1", node_name="browser_agent", worker_id="w1", lease_id="l1",
        assigned_at=utc_now(),
    )


def test_export_cluster_json_round_trips() -> None:
    payload = export_cluster_json([_worker()], [_assignment()], ClusterStatistics(generated_at=utc_now()))
    parsed = json.loads(payload)
    assert parsed["workers"][0]["worker_id"] == "w1"
    assert parsed["assignments"][0]["assignment_id"] == "a1"
    assert "statistics" in parsed


def test_export_cluster_mermaid_includes_worker_and_assignment() -> None:
    mermaid = export_cluster_mermaid([_worker()], [_assignment()])
    assert "flowchart LR" in mermaid
    assert "w1" in mermaid
    assert "s1" in mermaid
