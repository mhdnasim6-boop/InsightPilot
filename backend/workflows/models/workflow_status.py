"""WorkflowStatus: the lifecycle of a Workflow and of one WorkflowExecution.

A new enum, not a reuse of ``PlanStatus`` — deliberately, mirroring
``NodeStatus``'s own precedent (Phase 27): a workflow has genuinely
different states (``OPTIMIZED`` sits between validation and readiness,
reflecting the adaptive-optimization pass this layer adds) than the
``ExecutionPlan``/``ExecutionState`` it ultimately delegates to.
"""

from enum import Enum


class WorkflowStatus(str, Enum):
    """Lifecycle states of a Workflow / WorkflowExecution."""

    DRAFT = "draft"
    VALIDATED = "validated"
    OPTIMIZED = "optimized"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
