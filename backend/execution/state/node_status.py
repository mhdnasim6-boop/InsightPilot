"""NodeStatus: the lifecycle of one ExecutionStep within a DAG execution.

A new enum, not a reuse of ``ExecutionStatus``/``PlanStatus`` — deliberately.
``ExecutionStatus`` describes a whole LangGraph run; ``PlanStatus`` describes
a whole plan's lifecycle. A DAG node has a genuinely different lifecycle:
it can be blocked on dependencies not yet done (``PENDING``), blocked on a
free execution-pool slot once its dependencies *are* done (``QUEUED``), or
blocked on a pending human approval (``PAUSED``) while sibling branches keep
running — none of which the existing two enums distinguish, and none of
which should be added to those shared enums just for this module's sake.
"""

from enum import Enum


class NodeStatus(str, Enum):
    """Lifecycle states of one step within a DAG execution."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
