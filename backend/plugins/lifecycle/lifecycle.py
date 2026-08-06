"""PluginState: the lifecycle every discovered plugin moves through, plus
PluginRecord — the one place PluginRegistry keeps a plugin's current
state, its manifest, what it contributed, and why it failed (if it did).

A new state enum, not a reuse of ``NodeStatus``/``PlanStatus`` —
deliberately, mirroring ``NodeStatus``'s own precedent (Phase 27): a
plugin's lifecycle is genuinely different from a DAG node's or a plan's
(``DISCOVERED``/``VALIDATED`` have no equivalent in either), so it earns
its own vocabulary rather than overloading an existing one.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind


class PluginState(str, Enum):
    """One discovered plugin's lifecycle, start to finish."""

    DISCOVERED = "discovered"
    VALIDATED = "validated"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    REGISTERED = "registered"
    FAILED = "failed"
    UNLOADED = "unloaded"


class RegisteredExtension(BaseModel):
    """One thing a plugin contributed — recorded for introspection (REST/frontend)."""

    model_config = ConfigDict(frozen=True)

    kind: ExtensionKind
    name: str


class PluginRecord(BaseModel):
    """PluginRegistry's own complete, point-in-time view of one plugin."""

    model_config = ConfigDict(frozen=True)

    manifest: PluginManifest
    state: PluginState
    source_path: str
    extensions: list[RegisteredExtension] = Field(default_factory=list)
    error: str | None = None
    updated_at: datetime
