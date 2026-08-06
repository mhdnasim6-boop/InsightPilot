"""Tests for backend.dependencies.operations: singleton caching, and that
resolve_startup_manager()/resolve_shutdown_manager() (the manual,
lifespan-only resolution path — see that module's own docstring) produce
the exact same singletons a real request's Depends(get_startup_manager)
would.

Mirrors tests/test_mcp_dependencies.py's own pattern: provider functions
with a Depends(...)-defaulted parameter only resolve correctly through
FastAPI's own request handling, so every call here passes dependencies
explicitly instead.
"""

from collections.abc import Iterator

import pytest

from backend.dependencies.observability import (
    get_observability_service,
    get_trace_store,
)
from backend.dependencies.operations import (
    get_configuration_loader,
    get_configuration_validator,
    get_shutdown_manager,
    get_startup_manager,
    resolve_shutdown_manager,
    resolve_startup_manager,
)
from backend.dependencies.plugins import get_plugin_registry
from backend.dependencies.realtime import resolve_realtime_service
from backend.dependencies.tools import get_tool_registry
from backend.operations.startup.shutdown_manager import ShutdownManager
from backend.operations.startup.startup_manager import StartupManager


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    get_startup_manager.cache_clear()
    get_shutdown_manager.cache_clear()
    yield
    get_startup_manager.cache_clear()
    get_shutdown_manager.cache_clear()


def test_get_configuration_loader_and_validator_are_singletons() -> None:
    assert get_configuration_loader() is get_configuration_loader()
    assert get_configuration_validator() is get_configuration_validator()


def test_resolve_startup_manager_matches_a_request_style_depends_resolution() -> None:
    # The same keyword-argument-exact chain FastAPI's own Depends() resolution
    # would use for a real request — see backend.dependencies.plugins for the
    # Phase 33 precedent this mirrors.
    tool_registry = get_tool_registry()
    plugin_registry = get_plugin_registry(tool_registry=tool_registry, realtime_service=resolve_realtime_service())
    observability_service = get_observability_service(store=get_trace_store())
    from backend.dependencies.memory import get_memory_service, get_memory_store

    memory_service = get_memory_service(
        store=get_memory_store(), observability_service=observability_service,
        realtime_service=resolve_realtime_service(),
    )
    from backend.dependencies.execution import (
        get_execution_checkpoint_store,
        get_execution_pool,
        get_execution_task_registry,
    )

    request_style = get_startup_manager(
        tool_registry=tool_registry, plugin_registry=plugin_registry, memory_service=memory_service,
        observability_service=observability_service, execution_pool=get_execution_pool(),
        checkpoint_store=get_execution_checkpoint_store(), task_registry=get_execution_task_registry(),
        validator=get_configuration_validator(),
    )

    assert resolve_startup_manager() is request_style


def test_resolve_startup_manager_returns_the_real_type() -> None:
    assert isinstance(resolve_startup_manager(), StartupManager)


def test_startup_manager_running_actually_loads_plugins() -> None:
    manager = resolve_startup_manager()
    report = manager.run(profile="development")
    assert report.completed is True
    plugin_registry = get_plugin_registry(tool_registry=get_tool_registry(), realtime_service=resolve_realtime_service())
    assert any(record.manifest.id == "csv_statistics_plugin" for record in plugin_registry.list())


def test_resolve_shutdown_manager_matches_a_request_style_depends_resolution() -> None:
    plugin_registry = get_plugin_registry(tool_registry=get_tool_registry(), realtime_service=resolve_realtime_service())
    request_style = get_shutdown_manager(plugin_registry=plugin_registry)
    assert resolve_shutdown_manager() is request_style


def test_resolve_shutdown_manager_returns_the_real_type() -> None:
    assert isinstance(resolve_shutdown_manager(), ShutdownManager)


def test_shutdown_manager_running_unloads_active_plugins() -> None:
    tool_registry = get_tool_registry()
    plugin_registry = get_plugin_registry(tool_registry=tool_registry, realtime_service=resolve_realtime_service())
    plugin_registry.load()  # ensure the demo plugin is active first

    shutdown_report = resolve_shutdown_manager().run()

    assert shutdown_report.completed is True
    record = plugin_registry.lookup("csv_statistics_plugin")
    assert record.state.value == "unloaded"
    # Reload for any test that runs after this one in the same session.
    plugin_registry.load()
