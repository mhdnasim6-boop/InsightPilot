"""WorkerStatus: the lifecycle of one registered worker."""

from enum import Enum


class WorkerStatus(str, Enum):
    """Lifecycle states of a Worker."""

    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"
    FAILED = "failed"
    DRAINING = "draining"
