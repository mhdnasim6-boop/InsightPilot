"""Plugin endpoints: list/inspect installed plugins, and load/unload/reload them.

Thin HTTP wrappers only — every endpoint here is a direct call into
``PluginRegistry``, never a parallel implementation. Route order:
``/plugins/reload``/``/plugins/load``/``/plugins/unload`` are POSTs, so
they never collide with the GET ``/plugins/{plugin_id}`` route
regardless of registration order (different HTTP methods on the same
path shape don't need the literal-before-parameterized ordering
``/memory/statistics`` vs. ``/memory/{memory_id}`` needed — those were
both GETs).
"""

from fastapi import APIRouter, Depends

from backend.dependencies.plugins import get_plugin_registry
from backend.plugins.lifecycle.lifecycle import PluginRecord
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.schemas.plugin_request import PluginLoadRequest, PluginUnloadRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/plugins")


@router.get("", response_model=SuccessResponse[list[PluginRecord]], summary="List every known plugin")
async def list_plugins(
    plugin_registry: PluginRegistry = Depends(get_plugin_registry),
) -> SuccessResponse[list[PluginRecord]]:
    """Return every known plugin record (any lifecycle state), sorted by id."""
    return SuccessResponse.ok(data=plugin_registry.list(), message="Plugins fetched.")


@router.post("/reload", response_model=SuccessResponse[list[PluginRecord]], summary="Reload plugin(s)")
async def reload_plugins(
    request: PluginLoadRequest, plugin_registry: PluginRegistry = Depends(get_plugin_registry)
) -> SuccessResponse[list[PluginRecord]]:
    """Unload (if active) then load again — every plugin, or just ``request.plugin_id``."""
    records = plugin_registry.reload(request.plugin_id)
    return SuccessResponse.ok(data=records, message="Plugins reloaded.")


@router.post("/load", response_model=SuccessResponse[list[PluginRecord]], summary="Discover and load plugin(s)")
async def load_plugins(
    request: PluginLoadRequest, plugin_registry: PluginRegistry = Depends(get_plugin_registry)
) -> SuccessResponse[list[PluginRecord]]:
    """Discover and load every not-yet-active plugin, or just ``request.plugin_id``."""
    records = plugin_registry.load(request.plugin_id)
    return SuccessResponse.ok(data=records, message="Plugins loaded.")


@router.post("/unload", response_model=SuccessResponse[PluginRecord], summary="Unload one plugin")
async def unload_plugin(
    request: PluginUnloadRequest, plugin_registry: PluginRegistry = Depends(get_plugin_registry)
) -> SuccessResponse[PluginRecord]:
    """Shut down and unregister one active plugin. Raises PluginNotFoundError (404) if unknown."""
    record = plugin_registry.unload(request.plugin_id)
    return SuccessResponse.ok(data=record, message=f"Plugin '{request.plugin_id}' unloaded.")


@router.get("/{plugin_id}", response_model=SuccessResponse[PluginRecord], summary="Get one plugin")
async def get_plugin(
    plugin_id: str, plugin_registry: PluginRegistry = Depends(get_plugin_registry)
) -> SuccessResponse[PluginRecord]:
    """Fetch one plugin's current record. Raises PluginNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=plugin_registry.lookup(plugin_id), message="Plugin fetched.")
