"""Approval framework providers: stores, policy service, approval service."""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.dependencies.memory import get_memory_service
from backend.dependencies.realtime import get_realtime_service
from backend.memory.services.memory_service import MemoryService
from backend.realtime.publishers.approval_publisher import (
    RealtimePublishingApprovalService,
)
from backend.realtime.services.realtime_service import RealtimeService


@lru_cache
def get_approval_store() -> ApprovalStore:
    """Return the process-wide ApprovalStore singleton.

    Cached for the same reason as every other *Store in this codebase:
    an approval requested by one request must still be approvable/
    rejectable ("List pending approvals") in a later one.
    """
    return ApprovalStore()


@lru_cache
def get_execution_history_store() -> ExecutionHistoryStore:
    """Return the process-wide ExecutionHistoryStore singleton."""
    return ExecutionHistoryStore()


@lru_cache
def get_approval_policy_service() -> ApprovalPolicyService:
    """Return the process-wide ApprovalPolicyService singleton — one active policy at a time."""
    return ApprovalPolicyService()


@lru_cache
def get_approval_service(
    store: ApprovalStore = Depends(get_approval_store),
    history_store: ExecutionHistoryStore = Depends(get_execution_history_store),
    memory_service: MemoryService = Depends(get_memory_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> ApprovalService:
    """Provide the process-wide ApprovalService singleton.

    Cached — not just for its own stateless-wrapper efficiency, but
    because ``get_plan_executor()`` is itself cached and takes this as
    an argument: ``functools.lru_cache`` keys on argument identity, so
    an uncached ``ApprovalService`` here would silently defeat
    ``PlanExecutor``'s own cross-request caching, producing a fresh
    (and therefore paused-execution-amnesiac) ``PlanExecutor`` on every
    request — verified empirically before fixing. ``memory_service`` is
    itself cached too (``get_memory_service``), so this stays safe.

    Wrapped in ``RealtimePublishingApprovalService`` (Phase 37) before
    being returned — publishes ApprovalRequested/Granted/Rejected with no
    change to ``ApprovalService`` itself. Wrapping at this single cached
    source is what lets ``ApprovalRequested`` (raised only internally, by
    ``DAGScheduler.run()``) be observed at all — no REST call ever
    triggers it directly.
    """
    service: Any = RealtimePublishingApprovalService(
        ApprovalService(store, history_store, memory_service), realtime_service
    )
    return service
