"""FeatureFlagService: reads each flag's current value straight off
Settings — no separate store, no runtime toggle. "Flags are runtime
readable only" is satisfied literally: this service has no ``set()``.

Every flag's Settings field defaults to the always-on behavior every
earlier phase already ships, so the flags are purely observational in
this phase — nothing in Memory/Reflection/Adaptive Planning/Collaboration/
Plugin logic reads them, per this phase's own "do not modify" rule.
Wiring a flag to actually gate its subsystem is named as a future
extension, not attempted here.
"""

from backend.operations.exceptions import UnknownFeatureFlagError
from backend.operations.feature_flags.feature_flag import FeatureFlag, FeatureFlagName
from config.settings import Settings

_DESCRIPTIONS: dict[FeatureFlagName, str] = {
    FeatureFlagName.MEMORY_ENABLED: "Long-term memory and knowledge layer (backend/memory/).",
    FeatureFlagName.PLUGINS_ENABLED: "Plugin & Extension SDK discovery/loading (backend/plugins/).",
    FeatureFlagName.REFLECTION_ENABLED: "Post-execution self-reflection (backend/reflection/).",
    FeatureFlagName.ADAPTIVE_PLANNING_ENABLED: "Deterministic plan optimization (backend/adaptive/).",
    FeatureFlagName.BROWSER_AGENT_ENABLED: "External-context enrichment via the Browser Agent.",
    FeatureFlagName.MCP_ENABLED: "MCP server registration/discovery (backend/mcp/).",
}


class FeatureFlagService:
    """Read-only view over every ``*_enabled`` field on Settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_flags(self) -> list[FeatureFlag]:
        """Every known flag, in ``FeatureFlagName`` declaration order."""
        return [self._build(name) for name in FeatureFlagName]

    def is_enabled(self, name: FeatureFlagName) -> bool:
        """Whether one named flag is currently on."""
        return self._build(name).enabled

    def get(self, name: FeatureFlagName) -> FeatureFlag:
        """Fetch one flag by name. Raises UnknownFeatureFlagError for anything not in FeatureFlagName."""
        if name not in FeatureFlagName:
            raise UnknownFeatureFlagError(f"Unknown feature flag: '{name}'.")
        return self._build(name)

    def _build(self, name: FeatureFlagName) -> FeatureFlag:
        return FeatureFlag(name=name, enabled=bool(getattr(self._settings, name.value)), description=_DESCRIPTIONS[name])
