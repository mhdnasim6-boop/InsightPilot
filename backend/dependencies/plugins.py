"""Plugin SDK providers: the top-level PluginRegistry.

Cached, mirroring every other top-level registry in this codebase
(``ToolRegistry``, ``MemoryStore``): plugins are loaded once at process
startup (``backend.main``'s own ``lifespan()``) and must stay the same
instance across every subsequent request, or ``/plugins``' own view of
"what's loaded" would reset on every call.

``Settings`` is deliberately *not* one of this function's own
parameters, even though it's needed to build ``PluginLoader``/
``PluginValidator`` — ``Settings`` (a ``pydantic-settings`` model) isn't
hashable, so declaring it as an ``@lru_cache``'d function's own argument
raises ``TypeError: unhashable type`` the moment FastAPI resolves it
(caught live, via a real HTTP request, not assumed). This is why every
existing ``Settings``-dependent provider in this codebase
(``get_provider_factory``, ``get_health_service``) is deliberately left
*uncached* instead. ``get_plugin_registry`` needs to be cached (its
state must persist across requests), so it calls ``get_settings()``
directly in its own body — itself already ``@lru_cache``'d — rather
than declaring it as a ``Depends()`` parameter.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends

from backend.dependencies.realtime import get_realtime_service
from backend.dependencies.tools import get_tool_registry
from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.realtime.publishers.observability_publisher import (
    RealtimePublishingPluginRegistry,
)
from backend.realtime.services.realtime_service import RealtimeService
from backend.tools.registry.tool_registry import ToolRegistry
from config.settings import get_settings


@lru_cache
def get_plugin_registry(
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> PluginRegistry:
    """Return the process-wide PluginRegistry singleton.

    Wrapped in ``RealtimePublishingPluginRegistry`` (Phase 37) before
    being returned — publishes PluginLoaded/PluginUnloaded around
    ``load()``/``unload()`` with no change to ``PluginRegistry`` itself.
    """
    settings = get_settings()
    loader = PluginLoader(Path(settings.plugin_extensions_dir))
    validator = PluginValidator(settings.app_version)
    registry: Any = RealtimePublishingPluginRegistry(
        PluginRegistry(loader, validator, tool_registry), realtime_service
    )
    return registry
