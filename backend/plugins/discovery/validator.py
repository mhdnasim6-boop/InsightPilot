"""PluginValidator: manifest completeness, version compatibility, duplicate
ids, and dependency ordering — every check that must pass before a plugin
is initialized or registered.

``resolve_load_order()`` is a small, dedicated Kahn's-algorithm
implementation over plugin ids, not a reuse of
``backend.planning.validator.topology.topological_order()`` — that
function's input shape (``ExecutionStep``, keyed by ``step_id``) genuinely
differs from a plugin manifest graph keyed by ``PluginManifest.id``, so
reusing it would mean adapting one domain's shape to fit another's,
not reuse. Same algorithm, deliberately not the same function.
"""

from backend.plugins.exceptions import (
    DuplicatePluginError,
    PluginDependencyError,
    PluginValidationError,
    PluginVersionError,
)
from backend.plugins.manifest.plugin_manifest import PluginManifest


class PluginValidator:
    """Every check a discovered plugin must pass before it is loaded."""

    def __init__(self, app_version: str) -> None:
        self._app_version = app_version

    def validate_manifest(self, manifest: PluginManifest) -> None:
        """Raises PluginValidationError if any required field is missing/empty."""
        if not manifest.metadata.id.strip():
            raise PluginValidationError("Plugin manifest is missing a non-empty id.")
        if not manifest.metadata.name.strip():
            raise PluginValidationError(f"Plugin '{manifest.id}' manifest is missing a non-empty name.")
        if not manifest.metadata.version.strip():
            raise PluginValidationError(f"Plugin '{manifest.id}' manifest is missing a non-empty version.")
        if not manifest.metadata.author.strip():
            raise PluginValidationError(f"Plugin '{manifest.id}' manifest is missing a non-empty author.")
        if not manifest.provides:
            raise PluginValidationError(f"Plugin '{manifest.id}' declares no provided extensions.")

    def validate_version(self, manifest: PluginManifest) -> None:
        """Raises PluginVersionError unless the plugin's major version matches the running app's."""
        if _major(manifest.compatible_version) != _major(self._app_version):
            raise PluginVersionError(
                f"Plugin '{manifest.id}' declares compatibility with InsightPilot "
                f"{manifest.compatible_version}, incompatible with the running version {self._app_version}."
            )

    def validate_no_duplicate(self, manifest: PluginManifest, existing_ids: set[str]) -> None:
        """Raises DuplicatePluginError if ``manifest.id`` is already known."""
        if manifest.id in existing_ids:
            raise DuplicatePluginError(f"Plugin id '{manifest.id}' is already registered.")

    def resolve_load_order(self, manifests: list[PluginManifest]) -> list[str]:
        """Return a dependency-safe load order (dependencies before dependents).

        Raises PluginDependencyError for a dependency on an unknown plugin
        id, or a dependency cycle among ``manifests``.
        """
        by_id = {manifest.id: manifest for manifest in manifests}
        for manifest in manifests:
            for dependency in manifest.dependencies:
                if dependency not in by_id:
                    raise PluginDependencyError(
                        f"Plugin '{manifest.id}' depends on unknown plugin '{dependency}'."
                    )

        in_degree = {manifest.id: 0 for manifest in manifests}
        dependents: dict[str, list[str]] = {manifest.id: [] for manifest in manifests}
        for manifest in manifests:
            for dependency in manifest.dependencies:
                in_degree[manifest.id] += 1
                dependents[dependency].append(manifest.id)

        queue = sorted(plugin_id for plugin_id, degree in in_degree.items() if degree == 0)
        order: list[str] = []
        while queue:
            queue.sort()
            current = queue.pop(0)
            order.append(current)
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(manifests):
            cyclic = sorted(set(by_id) - set(order))
            raise PluginDependencyError(f"Dependency cycle detected among plugins: {', '.join(cyclic)}.")
        return order


def _major(version: str) -> str:
    return version.split(".")[0] if version else ""
