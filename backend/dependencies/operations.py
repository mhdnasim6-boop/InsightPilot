"""Operations layer providers: configuration loading/validation, feature
flags, health/readiness/diagnostics, and the startup/shutdown managers.

Mirrors ``backend.dependencies.plugins``' own established convention:
``Settings`` is never declared as a parameter of an ``@lru_cache``'d
function (it's a ``pydantic-settings`` model and isn't hashable — this
was confirmed to raise ``TypeError: unhashable type`` live, on a real
request, in Phase 33) — every cached provider below calls
``get_settings()`` directly in its own body instead.

``resolve_startup_manager()``/``resolve_shutdown_manager()`` exist so
``backend.main.lifespan`` can build the exact same singletons a real
request's own ``Depends(get_startup_manager)`` would resolve to, without
running inside FastAPI's own request-scoped dependency resolution — the
same manual, keyword-argument-exact resolution pattern
``backend.main.lifespan`` already established for ``get_plugin_registry``
in Phase 33 (``functools.lru_cache`` treats a positional call and a
keyword call as different cache keys, so every nested call below is
keyword, matching FastAPI's own ``call(**resolved_kwargs)`` convention
exactly).
"""

from functools import lru_cache

from fastapi import Depends

from backend.dependencies.execution import (
    get_execution_checkpoint_store,
    get_execution_pool,
    get_execution_task_registry,
)
from backend.dependencies.memory import get_memory_service, get_memory_store
from backend.dependencies.observability import (
    get_observability_service,
    get_trace_store,
)
from backend.dependencies.plugins import get_plugin_registry
from backend.dependencies.realtime import resolve_realtime_service
from backend.dependencies.services import get_health_service
from backend.dependencies.tools import get_tool_registry
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.operations.configuration.configuration_loader import ConfigurationLoader
from backend.operations.configuration.configuration_validator import (
    ConfigurationValidator,
)
from backend.operations.exceptions import ConfigurationValidationFailedError
from backend.operations.feature_flags.feature_flag_service import FeatureFlagService
from backend.operations.health.diagnostics import DiagnosticsService
from backend.operations.health.liveness import LivenessService
from backend.operations.health.readiness import ReadinessService
from backend.operations.startup.shutdown_manager import ShutdownManager, ShutdownStage
from backend.operations.startup.startup_manager import StartupManager, StartupStage
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.services.health_service import HealthService
from backend.tools.registry.tool_registry import ToolRegistry
from config.settings import Settings, get_settings


@lru_cache
def get_configuration_loader() -> ConfigurationLoader:
    """Return the process-wide ConfigurationLoader singleton. Stateless — cached only for identity reuse."""
    return ConfigurationLoader()


@lru_cache
def get_configuration_validator() -> ConfigurationValidator:
    """Return the process-wide ConfigurationValidator singleton. Stateless — cached only for identity reuse."""
    return ConfigurationValidator()


def get_liveness_service(health_service: HealthService = Depends(get_health_service)) -> LivenessService:
    """Provide a LivenessService bound to the existing HealthService. Uncached — HealthService itself is too."""
    return LivenessService(health_service)


def get_feature_flag_service(settings: Settings = Depends(get_settings)) -> FeatureFlagService:
    """Provide a FeatureFlagService bound to the current settings. Uncached, like get_health_service —
    Settings itself is safe as a plain (non-lru_cache'd) function's own Depends() parameter."""
    return FeatureFlagService(settings)


@lru_cache
def get_startup_manager(
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    plugin_registry: PluginRegistry = Depends(get_plugin_registry),
    memory_service: MemoryService = Depends(get_memory_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
    execution_pool: ExecutionPool = Depends(get_execution_pool),
    checkpoint_store: ExecutionCheckpointStore = Depends(get_execution_checkpoint_store),
    task_registry: ExecutionTaskRegistry = Depends(get_execution_task_registry),
    validator: ConfigurationValidator = Depends(get_configuration_validator),
) -> StartupManager:
    """Return the process-wide StartupManager singleton, wired with the "Configuration ->
    Plugin loading -> Registries -> Memory -> Observability -> Execution -> API ready"
    stages this phase names.

    Every stage's action is a bound method on (or a small closure over)
    an already-constructed, already-DI-resolved singleton — this
    function adds no new construction logic of its own, only ordering.
    "Memory"/"Observability"/"Execution" stages call a cheap, already-
    safe read (``.statistics()``, referencing the already-built
    singleton, reading the already-built stores) rather than constructing
    anything new — those singletons are already guaranteed to exist by
    the time this function's own Depends() parameters were resolved;
    the stage's job is only to prove that resolution actually succeeded
    and to give it a named, timed, reportable slot in the sequence.
    ``ExecutionService`` itself (the full six-agent-service DI chain) is
    deliberately never constructed here — it's designed to be built
    fresh per request (see ``backend.dependencies.execution``'s own
    docstring), and eagerly building it at startup would fight that
    designed lifecycle rather than respect it.
    """
    settings = get_settings()

    def _validate_configuration() -> None:
        result = validator.validate(settings)
        if not result.is_valid:
            messages = "; ".join(issue.message for issue in result.errors)
            raise ConfigurationValidationFailedError(f"Configuration validation failed: {messages}")

    stages = [
        StartupStage("configuration", _validate_configuration),
        StartupStage("plugin_loading", plugin_registry.load),
        StartupStage("registries", tool_registry.list_tools),
        StartupStage("memory", memory_service.statistics),
        StartupStage("observability", observability_service.list_traces),
        StartupStage("execution", lambda: (execution_pool, checkpoint_store, task_registry)),
        StartupStage("api_ready", lambda: None),
    ]
    return StartupManager(stages)


@lru_cache
def get_shutdown_manager(
    plugin_registry: PluginRegistry = Depends(get_plugin_registry),
) -> ShutdownManager:
    """Return the process-wide ShutdownManager singleton, reverse-ordered from startup.

    Every existing singleton this phase touches (``ToolRegistry``,
    ``MemoryStore``, ``ObservabilityService``'s ``TraceStore``, the
    Execution layer's stateful stores) is a pure in-process object with
    nothing external to release, so those stages are named (for
    operational visibility/symmetry with StartupManager) but are no-ops.
    ``PluginRegistry`` is the one real exception — a loaded plugin may
    hold real resources, and its own ``shutdown()`` deserves a genuine
    call, so "plugin_unloading" actually unloads every known plugin.
    """

    def _unload_all_plugins() -> None:
        for record in plugin_registry.list():
            plugin_registry.unload(record.manifest.id)

    stages = [
        ShutdownStage("execution", lambda: None),
        ShutdownStage("observability", lambda: None),
        ShutdownStage("memory", lambda: None),
        ShutdownStage("registries", lambda: None),
        ShutdownStage("plugin_unloading", _unload_all_plugins),
        ShutdownStage("configuration", lambda: None),
    ]
    return ShutdownManager(stages)


def get_readiness_service(startup_manager: StartupManager = Depends(get_startup_manager)) -> ReadinessService:
    """Provide a ReadinessService bound to the shared StartupManager."""
    return ReadinessService(startup_manager)


def get_diagnostics_service(
    settings: Settings = Depends(get_settings),
    plugin_registry: PluginRegistry = Depends(get_plugin_registry),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_flag_service: FeatureFlagService = Depends(get_feature_flag_service),
    configuration_validator: ConfigurationValidator = Depends(get_configuration_validator),
) -> DiagnosticsService:
    """Provide a DiagnosticsService bound to every collaborator it composes a report from."""
    return DiagnosticsService(
        settings=settings,
        plugin_registry=plugin_registry,
        tool_registry=tool_registry,
        memory_service=memory_service,
        feature_flag_service=feature_flag_service,
        configuration_validator=configuration_validator,
    )


def resolve_startup_manager() -> StartupManager:
    """Build the process-wide StartupManager outside a FastAPI request.

    Called exactly once, from ``backend.main.lifespan``. See this
    module's own docstring for why every call below is keyword-based.
    """
    tool_registry = get_tool_registry()
    plugin_registry = get_plugin_registry(tool_registry=tool_registry, realtime_service=resolve_realtime_service())
    trace_store = get_trace_store()
    observability_service = get_observability_service(store=trace_store)
    memory_service = get_memory_service(
        store=get_memory_store(), observability_service=observability_service,
        realtime_service=resolve_realtime_service(),
    )
    return get_startup_manager(
        tool_registry=tool_registry,
        plugin_registry=plugin_registry,
        memory_service=memory_service,
        observability_service=observability_service,
        execution_pool=get_execution_pool(),
        checkpoint_store=get_execution_checkpoint_store(),
        task_registry=get_execution_task_registry(),
        validator=get_configuration_validator(),
    )


def resolve_shutdown_manager() -> ShutdownManager:
    """Build the process-wide ShutdownManager outside a FastAPI request. See ``resolve_startup_manager()``."""
    return get_shutdown_manager(
        plugin_registry=get_plugin_registry(tool_registry=get_tool_registry(), realtime_service=resolve_realtime_service())
    )
