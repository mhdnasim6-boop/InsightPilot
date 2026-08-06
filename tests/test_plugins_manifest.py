"""Tests for backend.plugins.manifest: shapes, defaults, and immutability."""

from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata


def _metadata(**overrides: str) -> PluginMetadata:
    defaults = {"id": "p1", "name": "Plugin One", "version": "1.0.0", "author": "Someone"}
    defaults.update(overrides)
    return PluginMetadata(**defaults)  # type: ignore[arg-type]


def test_plugin_metadata_defaults() -> None:
    metadata = _metadata()
    assert metadata.description == ""
    assert metadata.tags == []


def test_plugin_metadata_is_frozen() -> None:
    metadata = _metadata()
    try:
        metadata.name = "changed"  # type: ignore[misc]
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


def test_plugin_manifest_id_passes_through_metadata() -> None:
    manifest = PluginManifest(
        metadata=_metadata(id="my_plugin"), compatible_version="0.1.0", provides=[ExtensionKind.TOOL]
    )
    assert manifest.id == "my_plugin"


def test_plugin_manifest_defaults() -> None:
    manifest = PluginManifest(metadata=_metadata(), compatible_version="0.1.0")
    assert manifest.provides == []
    assert manifest.dependencies == []


def test_extension_kind_has_every_documented_kind() -> None:
    expected = {
        "agent", "tool", "exporter", "visualization", "ai_provider",
        "memory_provider", "approval_policy", "analyzer", "optimizer", "mcp_adapter",
    }
    assert {kind.value for kind in ExtensionKind} == expected
