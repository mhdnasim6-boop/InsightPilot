"""Tests for backend.plugins.discovery: PluginLoader (real filesystem, no
mocking — writes real ``plugin.py`` files to a temp directory) and
PluginValidator (manifest completeness, version compatibility, duplicate
ids, dependency ordering and cycle detection).
"""

from pathlib import Path

import pytest

from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.exceptions import (
    DuplicatePluginError,
    PluginDependencyError,
    PluginValidationError,
    PluginVersionError,
)
from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata

_VALID_PLUGIN_SOURCE = '''
from backend.plugins.interfaces.plugin import Plugin
from backend.plugins.interfaces.plugin_context import PluginContext
from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata


class _StubPlugin(Plugin):
    def metadata(self) -> PluginManifest:
        return PluginManifest(
            metadata=PluginMetadata(id="{plugin_id}", name="{plugin_id}", version="1.0.0", author="Test"),
            compatible_version="0.1.0",
            provides=[ExtensionKind.TOOL],
        )

    def initialize(self) -> None:
        pass

    def register(self, context: PluginContext) -> None:
        pass

    def shutdown(self) -> None:
        pass


PLUGIN = _StubPlugin()
'''


def _write_plugin(extensions_dir: Path, folder_name: str, source: str) -> None:
    plugin_dir = extensions_dir / folder_name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(source)


def _metadata(plugin_id: str = "p1") -> PluginMetadata:
    return PluginMetadata(id=plugin_id, name=plugin_id, version="1.0.0", author="Test")


def _manifest(plugin_id: str = "p1", dependencies: list[str] | None = None, compatible_version: str = "0.1.0") -> PluginManifest:
    return PluginManifest(
        metadata=_metadata(plugin_id), compatible_version=compatible_version,
        provides=[ExtensionKind.TOOL], dependencies=dependencies or [],
    )


# -- PluginLoader ------------------------------------------------------------------------


def test_discover_returns_empty_list_when_directory_missing(tmp_path: Path) -> None:
    loader = PluginLoader(tmp_path / "does-not-exist")
    assert loader.discover() == []


def test_discover_finds_a_valid_plugin(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "my_plugin", _VALID_PLUGIN_SOURCE.format(plugin_id="my_plugin"))
    outcomes = PluginLoader(tmp_path).discover()
    assert len(outcomes) == 1
    assert outcomes[0].plugin is not None
    assert outcomes[0].plugin.metadata().id == "my_plugin"
    assert outcomes[0].error is None


def test_discover_ignores_folders_without_a_plugin_file(tmp_path: Path) -> None:
    (tmp_path / "not_a_plugin").mkdir()
    (tmp_path / "not_a_plugin" / "readme.txt").write_text("hello")
    assert PluginLoader(tmp_path).discover() == []


def test_discover_ignores_files_at_the_top_level(tmp_path: Path) -> None:
    (tmp_path / "stray_file.py").write_text("x = 1")
    assert PluginLoader(tmp_path).discover() == []


def test_discover_does_not_recurse_into_nested_folders(tmp_path: Path) -> None:
    nested = tmp_path / "outer" / "inner"
    nested.mkdir(parents=True)
    (nested / "plugin.py").write_text(_VALID_PLUGIN_SOURCE.format(plugin_id="nested_plugin"))
    # "outer" itself has no plugin.py directly inside it, only "outer/inner" does.
    assert PluginLoader(tmp_path).discover() == []


def test_discover_isolates_an_import_failure_and_continues(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "broken", "raise RuntimeError('boom')\n")
    _write_plugin(tmp_path, "healthy", _VALID_PLUGIN_SOURCE.format(plugin_id="healthy"))

    outcomes = PluginLoader(tmp_path).discover()

    by_folder = {Path(o.source_path).name: o for o in outcomes}
    assert by_folder["broken"].plugin is None
    assert "boom" in (by_folder["broken"].error or "")
    assert by_folder["healthy"].plugin is not None


def test_discover_reports_a_missing_plugin_attribute(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "no_attr", "x = 1\n")
    outcomes = PluginLoader(tmp_path).discover()
    assert outcomes[0].plugin is None
    assert "PLUGIN" in (outcomes[0].error or "")


# -- PluginValidator ------------------------------------------------------------------------


def test_validate_manifest_rejects_empty_id() -> None:
    manifest = PluginManifest(
        metadata=PluginMetadata(id="", name="x", version="1.0.0", author="a"), compatible_version="0.1.0",
        provides=[ExtensionKind.TOOL],
    )
    with pytest.raises(PluginValidationError):
        PluginValidator("0.1.0").validate_manifest(manifest)


def test_validate_manifest_rejects_no_provides() -> None:
    manifest = PluginManifest(metadata=_metadata(), compatible_version="0.1.0", provides=[])
    with pytest.raises(PluginValidationError):
        PluginValidator("0.1.0").validate_manifest(manifest)


def test_validate_manifest_accepts_a_complete_manifest() -> None:
    PluginValidator("0.1.0").validate_manifest(_manifest())  # does not raise


def test_validate_version_accepts_matching_major_version() -> None:
    PluginValidator("0.1.5").validate_version(_manifest(compatible_version="0.1.0"))  # does not raise


def test_validate_version_rejects_mismatched_major_version() -> None:
    with pytest.raises(PluginVersionError):
        PluginValidator("1.0.0").validate_version(_manifest(compatible_version="0.1.0"))


def test_validate_no_duplicate_rejects_known_id() -> None:
    with pytest.raises(DuplicatePluginError):
        PluginValidator("0.1.0").validate_no_duplicate(_manifest("p1"), {"p1"})


def test_validate_no_duplicate_accepts_unknown_id() -> None:
    PluginValidator("0.1.0").validate_no_duplicate(_manifest("p1"), {"p2"})  # does not raise


def test_resolve_load_order_orders_dependencies_first() -> None:
    manifests = [_manifest("b", dependencies=["a"]), _manifest("a")]
    order = PluginValidator("0.1.0").resolve_load_order(manifests)
    assert order == ["a", "b"]


def test_resolve_load_order_rejects_unknown_dependency() -> None:
    with pytest.raises(PluginDependencyError):
        PluginValidator("0.1.0").resolve_load_order([_manifest("a", dependencies=["ghost"])])


def test_resolve_load_order_rejects_a_cycle() -> None:
    manifests = [_manifest("a", dependencies=["b"]), _manifest("b", dependencies=["a"])]
    with pytest.raises(PluginDependencyError):
        PluginValidator("0.1.0").resolve_load_order(manifests)


def test_resolve_load_order_is_deterministic_for_independent_plugins() -> None:
    manifests = [_manifest("z"), _manifest("a"), _manifest("m")]
    order = PluginValidator("0.1.0").resolve_load_order(manifests)
    assert order == ["a", "m", "z"]
