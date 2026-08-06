"""PluginManifest: everything PluginValidator/PluginRegistry need to decide
whether a discovered plugin is safe to load, and in what order.

``compatible_version`` is compared against ``Settings.app_version`` by
major version only (the same coarse compatibility guarantee semver
itself promises) — see ``discovery/validator.py``. ``dependencies`` are
other plugins' ``PluginMetadata.id`` values this plugin must be loaded
after; ``PluginValidator`` detects both a missing dependency and a cycle
before any plugin in the batch is instantiated.
"""

from pydantic import BaseModel, ConfigDict, Field

from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata


class PluginManifest(BaseModel):
    """A plugin's complete, declarative self-description."""

    model_config = ConfigDict(frozen=True)

    metadata: PluginMetadata
    compatible_version: str
    provides: list[ExtensionKind] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    @property
    def id(self) -> str:
        """Convenience passthrough — ``PluginRegistry`` keys everything by this."""
        return self.metadata.id
