"""Plugin: the abstract contract every third-party extension must satisfy.

Mirrors this codebase's own recurring "one ABC every implementation
conforms to" pattern (``Tool``, ``ChartGenerator``, ``AIProvider``,
``CleaningRule``) — a plugin author subclasses this, nothing else.
``PluginRegistry`` calls exactly these four methods, in exactly this
order, and never anything else on a plugin instance — no
``inspect.getmembers()``, no monkeypatching, per this phase's own
constraints.
"""

from abc import ABC, abstractmethod

from backend.plugins.interfaces.plugin_context import PluginContext
from backend.plugins.manifest.plugin_manifest import PluginManifest


class Plugin(ABC):
    """Contract every InsightPilot plugin must satisfy."""

    @abstractmethod
    def metadata(self) -> PluginManifest:
        """Return this plugin's manifest. Called first, before any other method."""

    @abstractmethod
    def initialize(self) -> None:
        """Perform any one-time setup this plugin needs before registering extensions.

        Called once, after ``metadata()`` has been validated, before
        ``register()``. Raising here fails this plugin only — see
        ``PluginRegistry.load_all()``.
        """

    @abstractmethod
    def register(self, context: PluginContext) -> None:
        """Register every extension this plugin provides, using only ``context``.

        Never reach into InsightPilot internals directly (no store
        access, no other plugin's objects) — everything this plugin
        needs to register with is already on ``context``.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Release anything ``initialize()``/``register()`` acquired. Called on unload."""
