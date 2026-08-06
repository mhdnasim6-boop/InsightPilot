"""DependencyReport: what's actually loaded/registered right now — plugins,
tools, and orchestration agents — read straight from the existing
PluginRegistry/ToolRegistry/GraphMetadata, never a separate tracked copy.
"""

from pydantic import BaseModel

from backend.orchestration.graph.metadata import GraphMetadata
from backend.plugins.lifecycle.lifecycle import PluginState
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.tools.registry.tool_registry import ToolRegistry


class DependencyReport(BaseModel):
    """A snapshot of every plugin/tool/agent currently registered."""

    loaded_plugins: list[str]
    failed_plugins: list[str]
    registered_tools: list[str]
    registered_agents: list[str]


def build_dependency_report(
    plugin_registry: PluginRegistry,
    tool_registry: ToolRegistry,
    graph_metadata: GraphMetadata | None = None,
) -> DependencyReport:
    """Build a dependency report from the live registries. ``graph_metadata`` is optional —
    building a GraphBuilder is a heavy, request-scoped operation (see
    ``backend.dependencies.orchestration.get_graph_builder``), so a caller
    without one handy (e.g. a unit test) still gets a complete report with
    an empty ``registered_agents`` list rather than being forced to
    construct one.
    """
    records = plugin_registry.list()
    return DependencyReport(
        loaded_plugins=[record.manifest.id for record in records if record.state == PluginState.REGISTERED],
        failed_plugins=[record.manifest.id for record in records if record.state == PluginState.FAILED],
        registered_tools=[tool.name for tool in tool_registry.list_tools()],
        registered_agents=[node.name for node in graph_metadata.nodes] if graph_metadata is not None else [],
    )
