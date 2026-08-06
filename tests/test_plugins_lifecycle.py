"""Tests for backend.plugins.lifecycle: PluginState, RegisteredExtension, PluginRecord."""

from backend.plugins.lifecycle.lifecycle import (
    PluginRecord,
    PluginState,
    RegisteredExtension,
)
from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata
from backend.utils.time import utc_now


def test_plugin_state_has_every_documented_state() -> None:
    expected = {"discovered", "validated", "loaded", "initialized", "registered", "failed", "unloaded"}
    assert {state.value for state in PluginState} == expected


def test_registered_extension_is_frozen() -> None:
    extension = RegisteredExtension(kind=ExtensionKind.TOOL, name="my_tool")
    try:
        extension.name = "changed"  # type: ignore[misc]
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


def test_plugin_record_defaults() -> None:
    manifest = PluginManifest(
        metadata=PluginMetadata(id="p1", name="p1", version="1.0.0", author="a"), compatible_version="0.1.0",
    )
    record = PluginRecord(manifest=manifest, state=PluginState.DISCOVERED, source_path="x", updated_at=utc_now())
    assert record.extensions == []
    assert record.error is None
