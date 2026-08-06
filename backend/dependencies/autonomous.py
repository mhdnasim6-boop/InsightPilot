"""Autonomous optimization providers: the analyzer/optimizer/healing pipeline and the
top-level AutonomousService.

Caching mirrors every prior phase's own established convention
(``backend.dependencies.federation``'s own docstring): the one genuinely
stateful collaborator, ``OptimizationReportStore`` (every
``OptimizationReport`` ever generated), is an ``@lru_cache``'d
process-wide singleton — a report generated on one request must still be
listable on the next. Every analyzer/optimizer/engine on top is
stateless and left uncached, mirroring ``get_federation_service``: cheap
to rebuild, and the only piece of state that must survive across
requests already lives in the cached store.
"""

from functools import lru_cache

from fastapi import Depends

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.autonomous.analyzers.distributed_analyzer import DistributedAnalyzer
from backend.autonomous.analyzers.execution_analyzer import ExecutionAnalyzer
from backend.autonomous.analyzers.federation_analyzer import FederationAnalyzer
from backend.autonomous.analyzers.observability_analyzer import ObservabilityAnalyzer
from backend.autonomous.analyzers.resource_analyzer import ResourceAnalyzer
from backend.autonomous.analyzers.workflow_analyzer import WorkflowAnalyzer
from backend.autonomous.healing.healing_validator import HealingValidator
from backend.autonomous.healing.recovery_strategy import RecoveryStrategyCatalog
from backend.autonomous.healing.self_healing_engine import SelfHealingEngine
from backend.autonomous.optimizer.bottleneck_detector import BottleneckDetector
from backend.autonomous.optimizer.execution_optimizer import ExecutionOptimizer
from backend.autonomous.optimizer.recommendation_engine import RecommendationEngine
from backend.autonomous.optimizer.resource_optimizer import ResourceOptimizer
from backend.autonomous.optimizer.workflow_optimizer import WorkflowOptimizer
from backend.autonomous.services.autonomous_service import (
    AutonomousService,
    OptimizationReportStore,
)
from backend.dependencies.adaptive import get_adaptive_planning_service
from backend.dependencies.distributed import get_distributed_execution_service
from backend.dependencies.federation import get_federation_service
from backend.dependencies.memory import get_memory_service
from backend.dependencies.observability import (
    get_metrics_service,
    get_observability_service,
)
from backend.dependencies.reflection import get_reflection_service
from backend.dependencies.security import get_audit_service
from backend.dependencies.workflows import get_workflow_service
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.federation.services.federation_service import FederationService
from backend.memory.services.memory_service import MemoryService
from backend.observability.metrics.metrics_service import MetricsService
from backend.observability.services.observability_service import ObservabilityService
from backend.reflection.services.reflection_service import ReflectionService
from backend.security.audit.audit_service import AuditService
from backend.workflows.services.workflow_service import WorkflowService


@lru_cache
def get_optimization_report_store() -> OptimizationReportStore:
    """Return the process-wide OptimizationReportStore singleton — every generated
    report lives here."""
    return OptimizationReportStore()


def get_bottleneck_detector() -> BottleneckDetector:
    """Provide a BottleneckDetector wired to all six stateless analyzers."""
    return BottleneckDetector(
        execution_analyzer=ExecutionAnalyzer(), workflow_analyzer=WorkflowAnalyzer(),
        federation_analyzer=FederationAnalyzer(), distributed_analyzer=DistributedAnalyzer(),
        observability_analyzer=ObservabilityAnalyzer(), resource_analyzer=ResourceAnalyzer(),
    )


def get_self_healing_engine() -> SelfHealingEngine:
    """Provide a SelfHealingEngine wired to the RecoveryStrategyCatalog and HealingValidator."""
    return SelfHealingEngine(RecoveryStrategyCatalog(), HealingValidator())


def get_autonomous_service(
    store: OptimizationReportStore = Depends(get_optimization_report_store),
    bottleneck_detector: BottleneckDetector = Depends(get_bottleneck_detector),
    self_healing_engine: SelfHealingEngine = Depends(get_self_healing_engine),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    adaptive_planning_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
    metrics_service: MetricsService = Depends(get_metrics_service),
    reflection_service: ReflectionService = Depends(get_reflection_service),
    memory_service: MemoryService = Depends(get_memory_service),
    distributed_execution_service: DistributedExecutionService = Depends(get_distributed_execution_service),
    federation_service: FederationService = Depends(get_federation_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> AutonomousService:
    """Provide the AutonomousService — the only object anything should use to run an
    analysis pass or read back optimization reports/recommendations/statistics.

    Deliberately uncached itself, mirroring ``get_federation_service``:
    the only piece of state that must survive across requests already
    lives in the cached ``OptimizationReportStore`` this function is
    handed. ``workflow_service`` here is the fully-decorated
    ``FederationCoordinator(RealtimePublishingWorkflowService(...))``
    chain from ``get_workflow_service()`` — this service only ever calls
    its own read-only ``.statistics()``, so which decorators wrap it is
    irrelevant to correctness.
    """
    return AutonomousService(
        store=store, bottleneck_detector=bottleneck_detector, execution_optimizer=ExecutionOptimizer(),
        workflow_optimizer=WorkflowOptimizer(), resource_optimizer=ResourceOptimizer(),
        recommendation_engine=RecommendationEngine(), self_healing_engine=self_healing_engine,
        workflow_service=workflow_service, adaptive_planning_service=adaptive_planning_service,
        observability_service=observability_service, metrics_service=metrics_service,
        reflection_service=reflection_service, memory_service=memory_service,
        distributed_execution_service=distributed_execution_service, federation_service=federation_service,
        audit_service=audit_service,
    )
