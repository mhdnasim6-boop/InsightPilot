"""Planning providers: validator, optimizer, executor, planning service."""

from functools import lru_cache

from fastapi import Depends

from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.dependencies.approval import (
    get_approval_policy_service,
    get_approval_service,
)
from backend.dependencies.observability import get_observability_service
from backend.dependencies.orchestration import get_orchestration_service
from backend.observability.services.observability_service import ObservabilityService
from backend.planning.events.bus import PlanEventBus
from backend.planning.executor.executor import PlanExecutor
from backend.planning.optimizer.base import PlanOptimizer
from backend.planning.optimizer.default import DefaultPlanOptimizer
from backend.planning.validator.validator import PlanValidator
from backend.services.orchestration_service import OrchestrationService
from backend.services.planning_service import PlanningService


@lru_cache
def get_plan_event_bus() -> PlanEventBus:
    """Return the process-wide planning event bus singleton.

    Shared across every plan so a listener registered once observes the
    full lifecycle (PlanCreated through PlanCompleted/PlanFailed).
    """
    return PlanEventBus()


@lru_cache
def get_plan_validator() -> PlanValidator:
    """Return the process-wide PlanValidator singleton (stateless, safe to share)."""
    return PlanValidator()


@lru_cache
def get_plan_optimizer() -> PlanOptimizer:
    """Return the process-wide default PlanOptimizer singleton (stateless, safe to share)."""
    return DefaultPlanOptimizer()


@lru_cache
def get_plan_executor(
    event_bus: PlanEventBus = Depends(get_plan_event_bus),
    approval_service: ApprovalService = Depends(get_approval_service),
    approval_policy_service: ApprovalPolicyService = Depends(get_approval_policy_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
) -> PlanExecutor:
    """Return the process-wide PlanExecutor singleton.

    Cached like ExecutionEngine: tracked (and now possibly paused) plans
    must stay inspectable/resumable across requests, not just within the
    one that started them. Every plan it runs now also gets a full
    ExecutionTrace, via the same optional-collaborator pattern
    ``approval_service`` already established.
    """
    return PlanExecutor(event_bus, approval_service, approval_policy_service, observability_service)


def get_planning_service(
    validator: PlanValidator = Depends(get_plan_validator),
    optimizer: PlanOptimizer = Depends(get_plan_optimizer),
    executor: PlanExecutor = Depends(get_plan_executor),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
    event_bus: PlanEventBus = Depends(get_plan_event_bus),
) -> PlanningService:
    """Provide the PlanningService — the only object that should be used for plan orchestration."""
    return PlanningService(validator, optimizer, executor, orchestration_service, event_bus)
