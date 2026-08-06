"""export_cluster_json: JSON export of the whole worker fleet + active assignments."""

import json

from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.models.worker import Worker


def export_cluster_json(
    workers: list[Worker], assignments: list[TaskAssignment], statistics: ClusterStatistics
) -> str:
    """Serialize every worker, every active task assignment, and cluster statistics as one JSON document."""
    payload = {
        "statistics": statistics.model_dump(mode="json"),
        "workers": [worker.model_dump(mode="json") for worker in workers],
        "assignments": [assignment.model_dump(mode="json") for assignment in assignments],
    }
    return json.dumps(payload, indent=2)
