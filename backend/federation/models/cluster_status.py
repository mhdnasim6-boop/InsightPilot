"""ClusterStatus: the lifecycle of one registered cluster."""

from enum import Enum


class ClusterStatus(str, Enum):
    """Lifecycle states of a Cluster."""

    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    FAILED = "failed"
