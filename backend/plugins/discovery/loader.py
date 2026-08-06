"""PluginLoader: filesystem discovery, immediate subfolders only, no recursion.

Convention, not reflection: every plugin folder must contain a
``plugin.py`` module exposing one module-level attribute named
``PLUGIN`` (a ``Plugin`` instance). Finding it is one fixed-name
``importlib`` load plus one ``getattr()`` by a known name — never
``inspect.getmembers()``-based scanning, never monkeypatching. This is
the same fixed-entry-point convention pytest/Airflow plugins use.

Import failures are caught per folder and returned as a failed
``DiscoveryOutcome`` rather than raised — one bad plugin file must never
stop the rest of the directory from being discovered.
"""

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from backend.plugins.interfaces.plugin import Plugin

_ENTRY_MODULE_FILENAME = "plugin.py"
_ENTRY_ATTRIBUTE_NAME = "PLUGIN"


@dataclass(frozen=True)
class DiscoveryOutcome:
    """One discovered folder's outcome — exactly one of ``plugin``/``error`` is set."""

    source_path: str
    plugin: Plugin | None
    error: str | None


class PluginLoader:
    """Scans one directory's immediate subfolders for ``plugin.py:PLUGIN`` entry points."""

    def __init__(self, extensions_dir: Path) -> None:
        self._extensions_dir = extensions_dir

    def discover(self) -> list[DiscoveryOutcome]:
        """Import every immediate subfolder's plugin entry point, in name order."""
        if not self._extensions_dir.is_dir():
            return []

        outcomes: list[DiscoveryOutcome] = []
        for entry in sorted(self._extensions_dir.iterdir(), key=lambda path: path.name):
            if not entry.is_dir():
                continue
            entry_file = entry / _ENTRY_MODULE_FILENAME
            if not entry_file.is_file():
                continue
            outcomes.append(self._load_one(entry, entry_file))
        return outcomes

    def _load_one(self, folder: Path, entry_file: Path) -> DiscoveryOutcome:
        source_path = str(folder)
        module_name = f"insightpilot_plugin_{folder.name}"
        spec = importlib.util.spec_from_file_location(module_name, entry_file)
        if spec is None or spec.loader is None:
            return DiscoveryOutcome(source_path, None, f"Could not build an import spec for '{entry_file}'.")

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - one bad plugin module must not stop discovery
            return DiscoveryOutcome(source_path, None, f"{type(exc).__name__}: {exc}")

        plugin = getattr(module, _ENTRY_ATTRIBUTE_NAME, None)
        if not isinstance(plugin, Plugin):
            return DiscoveryOutcome(
                source_path, None, f"'{entry_file}' does not expose a '{_ENTRY_ATTRIBUTE_NAME}' Plugin instance."
            )
        return DiscoveryOutcome(source_path, plugin, None)
