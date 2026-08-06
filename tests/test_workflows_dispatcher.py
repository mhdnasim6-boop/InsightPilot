"""Tests for WorkflowDispatcher: dynamic agent/tool/plugin discovery — every
name comes from a real, live registry, never a hardcoded list."""

from pathlib import Path

from pydantic import BaseModel

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.plugins.discovery.loader import PluginLoader
from backend.plugins.discovery.validator import PluginValidator
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.tools.base.tool import Tool
from backend.tools.registry.tool_registry import ToolRegistry
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher


class _FakeAgentNode(OrchestrationNode):
    name = "fake_agent"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


class _ToolInput(BaseModel):
    value: str


class _ToolOutput(BaseModel):
    value: str


class _FakeTool(Tool[_ToolInput, _ToolOutput]):
    name = "fake_tool"
    description = "A fake tool for testing."
    input_model = _ToolInput
    output_model = _ToolOutput

    async def execute(self, tool_input: _ToolInput) -> _ToolOutput:
        return _ToolOutput(value=tool_input.value)


def _dispatcher(tmp_path: Path) -> WorkflowDispatcher:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode())
    graph_builder.set_entry_point("fake_agent")
    capability_registry = AgentCapabilityRegistry(graph_builder)

    tool_registry = ToolRegistry()
    tool_registry.register(_FakeTool())

    plugin_registry = PluginRegistry(PluginLoader(tmp_path / "extensions"), PluginValidator("0.1.0"), tool_registry)

    return WorkflowDispatcher(capability_registry, tool_registry, plugin_registry)


def test_discover_agents_returns_real_registered_nodes(tmp_path: Path) -> None:
    agents = _dispatcher(tmp_path).discover_agents()
    assert [a.name for a in agents] == ["fake_agent"]


def test_discover_agent_names_returns_a_set_of_names(tmp_path: Path) -> None:
    names = _dispatcher(tmp_path).discover_agent_names()
    assert names == {"fake_agent"}


def test_discover_tools_returns_real_registered_tools(tmp_path: Path) -> None:
    tools = _dispatcher(tmp_path).discover_tools()
    assert tools == ["fake_tool"]


def test_discover_plugins_returns_empty_with_no_plugins_loaded(tmp_path: Path) -> None:
    assert _dispatcher(tmp_path).discover_plugins() == []


def test_is_known_agent_is_true_for_a_real_agent(tmp_path: Path) -> None:
    assert _dispatcher(tmp_path).is_known_agent("fake_agent") is True


def test_is_known_agent_is_false_for_an_unknown_name(tmp_path: Path) -> None:
    assert _dispatcher(tmp_path).is_known_agent("does_not_exist") is False


def test_never_hardcodes_a_specific_agent_name(tmp_path: Path) -> None:
    """Proof, not assumption: renaming the fake node changes discover_agents()'s
    output with zero changes to WorkflowDispatcher itself."""
    graph_builder = GraphBuilder()

    class _RenamedAgentNode(OrchestrationNode):
        name = "totally_different_name"

        async def execute(self, state: InsightPilotState) -> InsightPilotState:
            return state

    graph_builder.add_node(_RenamedAgentNode())
    graph_builder.set_entry_point("totally_different_name")
    capability_registry = AgentCapabilityRegistry(graph_builder)
    tool_registry = ToolRegistry()
    plugin_registry = PluginRegistry(PluginLoader(tmp_path / "extensions"), PluginValidator("0.1.0"), tool_registry)

    dispatcher = WorkflowDispatcher(capability_registry, tool_registry, plugin_registry)
    assert dispatcher.discover_agent_names() == {"totally_different_name"}
