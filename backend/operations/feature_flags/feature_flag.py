"""FeatureFlagName / FeatureFlag: the closed vocabulary of flags this
phase names, and the shape each one reports itself in.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class FeatureFlagName(str, Enum):
    """Every feature flag InsightPilot currently exposes."""

    MEMORY_ENABLED = "memory_enabled"
    PLUGINS_ENABLED = "plugins_enabled"
    REFLECTION_ENABLED = "reflection_enabled"
    ADAPTIVE_PLANNING_ENABLED = "adaptive_planning_enabled"
    BROWSER_AGENT_ENABLED = "browser_agent_enabled"
    MCP_ENABLED = "mcp_enabled"


class FeatureFlag(BaseModel):
    """One flag's current, read-only state."""

    model_config = ConfigDict(frozen=True)

    name: FeatureFlagName
    enabled: bool
    description: str
