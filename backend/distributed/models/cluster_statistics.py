"""ClusterStatistics: a point-in-time aggregate view of the whole worker fleet."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClusterStatistics(BaseModel):
    """Aggregate counts across every registered worker and the task queues."""

    model_config = ConfigDict(frozen=True)

    total_workers: int = 0
    online_workers: int = 0
    busy_workers: int = 0
    offline_workers: int = 0
    failed_workers: int = 0
    draining_workers: int = 0
    total_active_tasks: int = 0
    total_capacity: int = 0
    queue_depth: int = 0
    retry_queue_depth: int = 0
    generated_at: datetime
