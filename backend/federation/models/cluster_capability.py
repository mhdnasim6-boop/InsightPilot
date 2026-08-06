"""ClusterCapability: what one cluster advertises it can run.

Self-declared at registration time for a remote cluster (a genuinely
different InsightPilot deployment may support agents/plugins/MCP
adapters this process has never heard of — that heterogeneity is the
whole point of federation); derived from the real, live local registries
(`AgentCapabilityRegistry`, `PluginRegistry`, `MCPService`) for the local
cluster — see `FederationService`'s own docstring for how the local
cluster's own record is built.
"""

from pydantic import BaseModel, ConfigDict, Field


class ClusterCapability(BaseModel):
    """One cluster's declared agents, plugins, MCP adapters, and workload limits."""

    model_config = ConfigDict(frozen=True)

    supported_agents: list[str] = Field(default_factory=list)
    supported_plugins: list[str] = Field(default_factory=list)
    supported_mcp_adapters: list[str] = Field(default_factory=list)
    maximum_workflow_size: int = Field(default=100, gt=0)
    maximum_concurrent_executions: int = Field(default=1, gt=0)
    supported_workflow_features: list[str] = Field(default_factory=list)
