"""Orchestration lifecycle events."""

from datetime import datetime

from pydantic import BaseModel


class OrchestrationEvent(BaseModel):
    """Base class for all orchestration events."""

    execution_id: str
    timestamp: datetime


class ExecutionStarted(OrchestrationEvent):
    """A graph execution has begun."""

    session_id: str | None = None


class NodeStarted(OrchestrationEvent):
    """A node has begun executing."""

    node_name: str


class NodeCompleted(OrchestrationEvent):
    """A node finished executing successfully."""

    node_name: str
    duration_ms: float


class ExecutionCompleted(OrchestrationEvent):
    """A graph execution finished successfully."""

    status: str
    duration_ms: float


class ExecutionFailed(OrchestrationEvent):
    """A graph execution failed or was cancelled."""

    error: str
    failed_node: str | None = None
