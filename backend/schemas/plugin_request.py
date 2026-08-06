"""Request bodies for the /plugins/* mutation endpoints.

``plugin_id: None`` means "every plugin" for ``/reload``/``/load``
(mirrors ``PluginRegistry.load()``/``.reload()``'s own optional
parameter); ``/unload`` always requires one, since unloading "every
plugin" has no obviously safe meaning the way loading/reloading does.
"""

from pydantic import BaseModel


class PluginLoadRequest(BaseModel):
    """Body for POST /plugins/load and POST /plugins/reload."""

    plugin_id: str | None = None


class PluginUnloadRequest(BaseModel):
    """Body for POST /plugins/unload."""

    plugin_id: str
