"""Tests for PluginRegistry: the single public entry point orchestrating
discovery, validation, lifecycle transitions, and failure isolation —
every test here uses a real temp-directory PluginLoader, never a mock.
"""

from pathlib import Path

import pytest

from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.exceptions import PluginNotFoundError
from backend.plugins.lifecycle.lifecycle import PluginState
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.tools.registry.tool_registry import ToolRegistry

_PLUGIN_TEMPLATE = '''
from backend.plugins.interfaces.plugin import Plugin
from backend.plugins.interfaces.plugin_context import PluginContext
from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata
from backend.tools.base.tool import Tool
from pydantic import BaseModel


class _Input(BaseModel):
    value: int


class _Output(BaseModel):
    value: int


class _DemoTool(Tool[_Input, _Output]):
    name = "{tool_name}"
    description = "demo"
    input_model = _Input
    output_model = _Output

    async def execute(self, tool_input: _Input) -> _Output:
        return _Output(value=tool_input.value)


class _StubPlugin(Plugin):
    def metadata(self) -> PluginManifest:
        return PluginManifest(
            metadata=PluginMetadata(id="{plugin_id}", name="{plugin_id}", version="1.0.0", author="Test"),
            compatible_version="0.1.0",
            provides=[ExtensionKind.TOOL],
            dependencies={dependencies!r},
        )

    def initialize(self) -> None:
        {init_body}

    def register(self, context: PluginContext) -> None:
        context.register_tool(_DemoTool())

    def shutdown(self) -> None:
        {shutdown_body}


PLUGIN = _StubPlugin()
'''


def _write_plugin(
    extensions_dir: Path,
    folder_name: str,
    plugin_id: str,
    tool_name: str | None = None,
    dependencies: list[str] | None = None,
    init_body: str = "pass",
    shutdown_body: str = "pass",
) -> None:
    plugin_dir = extensions_dir / folder_name
    plugin_dir.mkdir(parents=True)
    source = _PLUGIN_TEMPLATE.format(
        plugin_id=plugin_id, tool_name=tool_name or f"{plugin_id}_tool", dependencies=dependencies or [],
        init_body=init_body, shutdown_body=shutdown_body,
    )
    (plugin_dir / "plugin.py").write_text(source)


def _registry(extensions_dir: Path) -> tuple[PluginRegistry, ToolRegistry]:
    tool_registry = ToolRegistry()
    registry = PluginRegistry(PluginLoader(extensions_dir), PluginValidator("0.1.0"), tool_registry)
    return registry, tool_registry


def test_load_registers_a_valid_plugin_and_its_tool(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "demo", "demo_plugin")
    registry, tool_registry = _registry(tmp_path)

    records = registry.load()

    assert len(records) == 1
    assert records[0].state == PluginState.REGISTERED
    assert [e.name for e in records[0].extensions] == ["demo_plugin_tool"]
    assert tool_registry.get("demo_plugin_tool") is not None


def test_load_is_idempotent_for_already_active_plugins(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "demo", "demo_plugin")
    registry, _ = _registry(tmp_path)
    registry.load()
    second_pass = registry.load()
    assert len(second_pass) == 1  # not duplicated, not reloaded


def test_load_with_a_specific_plugin_id_loads_only_that_one(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "a", "plugin_a")
    _write_plugin(tmp_path, "b", "plugin_b")
    registry, _ = _registry(tmp_path)

    registry.load("plugin_a")

    assert registry.lookup("plugin_a").state == PluginState.REGISTERED
    with pytest.raises(PluginNotFoundError):
        registry.lookup("plugin_b")


def test_load_with_unknown_plugin_id_raises() -> None:
    registry, _ = _registry(Path("/nonexistent"))
    with pytest.raises(PluginNotFoundError):
        registry.load("ghost")


def test_load_isolates_a_failing_plugin_and_still_loads_the_healthy_one(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "broken", "broken_plugin", init_body="raise RuntimeError('init failed')")
    _write_plugin(tmp_path, "healthy", "healthy_plugin")
    registry, tool_registry = _registry(tmp_path)

    records = registry.load()

    by_id = {r.manifest.id: r for r in records}
    assert by_id["broken_plugin"].state == PluginState.FAILED
    assert "init failed" in (by_id["broken_plugin"].error or "")
    assert by_id["healthy_plugin"].state == PluginState.REGISTERED
    assert tool_registry.get("healthy_plugin_tool") is not None


def test_load_rejects_duplicate_ids_across_folders(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "first", "same_id")
    _write_plugin(tmp_path, "second", "same_id")
    registry, _ = _registry(tmp_path)

    records = registry.load()

    # Exactly one record survives under that id; whichever loaded second failed as a duplicate.
    matching = [r for r in records if r.manifest.id == "same_id"]
    assert len(matching) == 1


def test_load_respects_dependency_order(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "b", "plugin_b", dependencies=["plugin_a"])
    _write_plugin(tmp_path, "a", "plugin_a")
    registry, _ = _registry(tmp_path)

    records = registry.load()

    assert all(r.state == PluginState.REGISTERED for r in records)


def test_load_fails_every_plugin_in_a_dependency_cycle(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "a", "plugin_a", dependencies=["plugin_b"])
    _write_plugin(tmp_path, "b", "plugin_b", dependencies=["plugin_a"])
    registry, _ = _registry(tmp_path)

    records = registry.load()

    assert all(r.state == PluginState.FAILED for r in records)
    assert all("cycle" in (r.error or "").lower() for r in records)


def test_load_fails_a_version_incompatible_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "old"
    plugin_dir.mkdir()
    source = _PLUGIN_TEMPLATE.format(
        plugin_id="old_plugin", tool_name="old_tool", dependencies=[], init_body="pass", shutdown_body="pass"
    ).replace('compatible_version="0.1.0"', 'compatible_version="9.9.9"')
    (plugin_dir / "plugin.py").write_text(source)
    registry, _ = _registry(tmp_path)

    records = registry.load()

    assert records[0].state == PluginState.FAILED
    assert "version" in (records[0].error or "").lower()


def test_unload_removes_the_plugins_tool_from_tool_registry(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "demo", "demo_plugin")
    registry, tool_registry = _registry(tmp_path)
    registry.load()

    record = registry.unload("demo_plugin")

    assert record.state == PluginState.UNLOADED
    with pytest.raises(Exception):  # noqa: B017 - ToolNotFoundError, not this package's concern
        tool_registry.get("demo_plugin_tool")


def test_unload_unknown_plugin_raises() -> None:
    registry, _ = _registry(Path("/nonexistent"))
    with pytest.raises(PluginNotFoundError):
        registry.unload("ghost")


def test_unload_isolates_a_failing_shutdown(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "demo", "demo_plugin", shutdown_body="raise RuntimeError('shutdown failed')")
    registry, _ = _registry(tmp_path)
    registry.load()

    record = registry.unload("demo_plugin")

    assert record.state == PluginState.FAILED
    assert "shutdown failed" in (record.error or "")


def test_reload_unloads_then_loads_again(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "demo", "demo_plugin")
    registry, tool_registry = _registry(tmp_path)
    registry.load()

    records = registry.reload()

    assert records[0].state == PluginState.REGISTERED
    assert tool_registry.get("demo_plugin_tool") is not None


def test_reload_a_specific_plugin_id(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "a", "plugin_a")
    _write_plugin(tmp_path, "b", "plugin_b")
    registry, _ = _registry(tmp_path)
    registry.load()

    records = registry.reload("plugin_a")

    assert {r.manifest.id for r in records} == {"plugin_a", "plugin_b"}
    assert registry.lookup("plugin_a").state == PluginState.REGISTERED
    assert registry.lookup("plugin_b").state == PluginState.REGISTERED


def test_list_returns_records_sorted_by_id(tmp_path: Path) -> None:
    _write_plugin(tmp_path, "z", "z_plugin")
    _write_plugin(tmp_path, "a", "a_plugin")
    registry, _ = _registry(tmp_path)
    registry.load()
    assert [r.manifest.id for r in registry.list()] == ["a_plugin", "z_plugin"]


def test_lookup_raises_for_unknown_plugin() -> None:
    registry, _ = _registry(Path("/nonexistent"))
    with pytest.raises(PluginNotFoundError):
        registry.lookup("ghost")
