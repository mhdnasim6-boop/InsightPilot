"""Lifecycle enum for execution plans.

Steps reuse ``backend.orchestration.state.state.ExecutionStatus`` instead
of defining a second, near-identical enum — a step, once dispatched,
literally becomes one orchestration execution.
"""

from enum import Enum


class PlanStatus(str, Enum):
    """Lifecycle states of an ExecutionPlan, from creation through completion."""

    DRAFT = "draft"
    VALIDATED = "validated"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
