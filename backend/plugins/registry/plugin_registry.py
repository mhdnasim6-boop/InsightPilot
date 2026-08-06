"""PluginRegistry: the only public entry point for the plugin system.

``load()``/``unload()``/``reload()``/``list()``/``lookup()`` — nothing
outside ``backend/plugins/`` should call ``PluginLoader``/``PluginValidator``
or touch a ``Plugin`` instance directly. Every failure — a bad import, a
missing manifest field, an incompatible version, a duplicate id, a
dependency cycle, or an exception raised by ``initialize()``/
``register()``/``shutdown()`` — is caught here and recorded as a
``PluginState.FAILED`` ``PluginRecord`` with its ``error`` message,
**never re-raised**: one bad plugin must never stop another plugin from
loading, and must never crash the platform.
"""

from backend.plugins.discovery.loader import DiscoveryOutcome, PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.exceptions import PluginError, PluginNotFoundError
from backend.plugins.interfaces.plugin import Plugin
from backend.plugins.interfaces.plugin_context import PluginContext
from backend.plugins.lifecycle.lifecycle import (
    PluginRecord,
    PluginState,
    RegisteredExtension,
)
from backend.plugins.manifest.plugin_manifest import PluginManifest
from backend.plugins.manifest.plugin_metadata import ExtensionKind, PluginMetadata
from backend.tools.registry.tool_registry import ToolRegistry
from backend.utils.time import utc_now

_ACTIVE_STATES = frozenset({PluginState.LOADED, PluginState.INITIALIZED, PluginState.REGISTERED})


class PluginRegistry:
    """Discovers, validates, loads, unloads, and reloads plugins — the only public entry point."""

    def __init__(self, loader: PluginLoader, validator: PluginValidator, tool_registry: ToolRegistry) -> None:
        self._loader = loader
        self._validator = validator
        self._tool_registry = tool_registry
        self._records: dict[str, PluginRecord] = {}
        self._instances: dict[str, Plugin] = {}

    def load(self, plugin_id: str | None = None) -> list[PluginRecord]:
        """Discover and load every not-yet-active plugin (or just ``plugin_id``, if given).

        Idempotent: a plugin whose id is already LOADED/INITIALIZED/
        REGISTERED is left untouched, never reloaded as a side effect.
        A folder that isn't ``plugin_id`` is excluded *before* validation
        when one is given, so it is never partially recorded — only the
        requested plugin's own outcome ever reaches ``_validate_outcome()``.
        """
        outcomes = self._loader.discover()
        if plugin_id is not None:
            outcomes = [outcome for outcome in outcomes if self._outcome_matches(outcome, plugin_id)]
            if not outcomes and plugin_id not in self._records:
                raise PluginNotFoundError(f"No plugin folder found providing id '{plugin_id}'.")

        active_ids = {pid for pid, record in self._records.items() if record.state in _ACTIVE_STATES}
        candidates: list[tuple[Plugin, PluginManifest, str]] = []
        for outcome in outcomes:
            candidate = self._validate_outcome(outcome, active_ids, {c[1].id for c in candidates})
            if candidate is None:
                continue
            candidates.append(candidate)

        self._load_candidates(candidates)
        return self.list()

    def _outcome_matches(self, outcome: DiscoveryOutcome, plugin_id: str) -> bool:
        if outcome.plugin is None:
            return False
        try:
            return outcome.plugin.metadata().id == plugin_id
        except Exception:  # noqa: BLE001 - a bad metadata() just means "doesn't match", handled at validate time otherwise
            return False

    def unload(self, plugin_id: str) -> PluginRecord:
        """Shut down and unregister one active plugin. Its tools are removed from ToolRegistry."""
        record = self.lookup(plugin_id)
        plugin = self._instances.get(plugin_id)
        if plugin is None:
            return self._set_state(record.manifest, PluginState.UNLOADED, record.source_path)

        try:
            plugin.shutdown()
        except Exception as exc:  # noqa: BLE001 - a bad shutdown() must not crash the platform
            return self._set_failed(record.source_path, record.manifest, f"shutdown() raised: {type(exc).__name__}: {exc}")

        for extension in record.extensions:
            if extension.kind == ExtensionKind.TOOL:
                self._tool_registry.unregister(extension.name)
        self._instances.pop(plugin_id, None)
        return self._set_state(record.manifest, PluginState.UNLOADED, record.source_path)

    def reload(self, plugin_id: str | None = None) -> list[PluginRecord]:
        """Unload (if active), then load again — every plugin, or just ``plugin_id``."""
        target_ids = [plugin_id] if plugin_id is not None else list(self._records.keys())
        for target_id in target_ids:
            record = self._records.get(target_id)
            if record is not None and record.state in _ACTIVE_STATES:
                self.unload(target_id)
        return self.load(plugin_id)

    def lookup(self, plugin_id: str) -> PluginRecord:
        """Fetch one plugin's current record. Raises PluginNotFoundError if unknown."""
        record = self._records.get(plugin_id)
        if record is None:
            raise PluginNotFoundError(f"No plugin found for '{plugin_id}'.")
        return record

    def _validate_outcome(
        self, outcome: DiscoveryOutcome, active_ids: set[str], pending_ids: set[str]
    ) -> tuple[Plugin, PluginManifest, str] | None:
        if outcome.plugin is None:
            self._set_failed(outcome.source_path, None, outcome.error or "Unknown discovery failure.")
            return None

        try:
            manifest = outcome.plugin.metadata()
        except Exception as exc:  # noqa: BLE001 - a bad metadata() must not crash discovery
            self._set_failed(outcome.source_path, None, f"metadata() raised: {type(exc).__name__}: {exc}")
            return None

        if manifest.id in active_ids:
            return None  # already active — idempotent, not an error

        try:
            self._validator.validate_manifest(manifest)
            self._validator.validate_version(manifest)
            self._validator.validate_no_duplicate(manifest, active_ids | pending_ids)
        except PluginError as exc:
            self._set_failed(outcome.source_path, manifest, str(exc))
            return None

        self._set_state(manifest, PluginState.VALIDATED, outcome.source_path)
        return outcome.plugin, manifest, outcome.source_path

    def _load_candidates(self, candidates: list[tuple[Plugin, PluginManifest, str]]) -> None:
        if not candidates:
            return

        manifests = [manifest for _, manifest, _ in candidates]
        try:
            order = self._validator.resolve_load_order(manifests)
        except PluginError as exc:
            for _, manifest, source_path in candidates:
                self._set_failed(source_path, manifest, str(exc))
            return

        by_id = {manifest.id: (plugin, manifest, source_path) for plugin, manifest, source_path in candidates}
        for plugin_id in order:
            plugin, manifest, source_path = by_id[plugin_id]
            self._load_one(plugin, manifest, source_path)

    def _load_one(self, plugin: Plugin, manifest: PluginManifest, source_path: str) -> None:
        self._set_state(manifest, PluginState.LOADED, source_path)
        try:
            plugin.initialize()
            self._set_state(manifest, PluginState.INITIALIZED, source_path)

            context = PluginContext(self._tool_registry)
            plugin.register(context)

            self._set_state(manifest, PluginState.REGISTERED, source_path, context.registered_extensions)
            self._instances[manifest.id] = plugin
        except Exception as exc:  # noqa: BLE001 - one bad plugin must never stop another from loading
            self._set_failed(source_path, manifest, f"{type(exc).__name__}: {exc}")

    def _set_state(
        self,
        manifest: PluginManifest,
        state: PluginState,
        source_path: str,
        extensions: list[RegisteredExtension] | None = None,
    ) -> PluginRecord:
        record = PluginRecord(
            manifest=manifest, state=state, source_path=source_path, extensions=extensions or [],
            error=None, updated_at=utc_now(),
        )
        self._records[manifest.id] = record
        return record

    def _set_failed(self, source_path: str, manifest: PluginManifest | None, error: str) -> PluginRecord:
        resolved_manifest = manifest or _placeholder_manifest(source_path)
        record = PluginRecord(
            manifest=resolved_manifest, state=PluginState.FAILED, source_path=source_path, extensions=[],
            error=error, updated_at=utc_now(),
        )
        self._records[resolved_manifest.id] = record
        return record

    # Defined last, deliberately: naming this method "list" rebinds that name
    # within this class body's own namespace for every line below it, which
    # would otherwise shadow the builtin `list` used in every other method's
    # own `list[...]` annotations above (Python evaluates annotations eagerly,
    # top to bottom, as each `def` statement executes) — caught by an actual
    # `TypeError: 'function' object is not subscriptable` at import time, not
    # a hypothetical.
    def list(self) -> list[PluginRecord]:
        """Every known plugin record (any state), sorted by id."""
        return sorted(self._records.values(), key=lambda record: record.manifest.id)


def _placeholder_manifest(source_path: str) -> PluginManifest:
    """A minimal manifest for a plugin that failed before it could produce one of its own."""
    return PluginManifest(
        metadata=PluginMetadata(id=source_path, name=source_path, version="0.0.0", author="unknown"),
        compatible_version="0.0.0",
        provides=[],
    )
