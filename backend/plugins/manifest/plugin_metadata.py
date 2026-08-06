"""PluginMetadata: a plugin's identity — the part of a manifest that never
affects loading logic, only how it's displayed/attributed.

``ExtensionKind`` is the closed vocabulary of everything a plugin can
``provide`` — deliberately a fixed enum, not an open string, so
``PluginContext``'s registration methods and ``PluginRegistry``'s own
catalog stay exhaustively typeable (no ``Any`` anywhere in this package).
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ExtensionKind(str, Enum):
    """Every kind of extension point a plugin may contribute to."""

    AGENT = "agent"
    TOOL = "tool"
    EXPORTER = "exporter"
    VISUALIZATION = "visualization"
    AI_PROVIDER = "ai_provider"
    MEMORY_PROVIDER = "memory_provider"
    APPROVAL_POLICY = "approval_policy"
    ANALYZER = "analyzer"
    OPTIMIZER = "optimizer"
    MCP_ADAPTER = "mcp_adapter"


class PluginMetadata(BaseModel):
    """A plugin's identity: who wrote it, what it's called, and what version."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    version: str
    author: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
