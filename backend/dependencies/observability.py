"""Observability providers: trace store, observability service, metrics service, exporters.

Mirrors the rest of this package's caching convention: ``TraceStore``
and ``ObservabilityService`` are process-wide singletons (like
``ToolRegistry``/``ApprovalStore``) — every trace, whichever request
started it, must stay inspectable across requests, not just within the
one that started it.
"""

from functools import lru_cache

from fastapi import Depends

from backend.observability.exporters.trace_exporter import TraceExporter
from backend.observability.metrics.metrics_service import MetricsService
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore


@lru_cache
def get_trace_store() -> TraceStore:
    """Return the process-wide TraceStore singleton."""
    return TraceStore()


@lru_cache
def get_observability_service(store: TraceStore = Depends(get_trace_store)) -> ObservabilityService:
    """Return the process-wide ObservabilityService singleton."""
    return ObservabilityService(store)


def get_metrics_service(
    observability_service: ObservabilityService = Depends(get_observability_service),
) -> MetricsService:
    """Provide a MetricsService bound to the shared ObservabilityService."""
    return MetricsService(observability_service)


def get_trace_exporter() -> TraceExporter:
    """Provide a TraceExporter — stateless, cheap to construct per request."""
    return TraceExporter()
