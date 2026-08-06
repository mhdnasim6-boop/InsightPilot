"""Unit tests for ToolRegistry: dynamic, name-keyed registration and lookup."""

import asyncio

import pytest
from pydantic import BaseModel

from backend.tools.base.tool import Tool
from backend.tools.exceptions import ToolNotFoundError
from backend.tools.registry.tool_registry import ToolRegistry


class _Input(BaseModel):
    value: int


class _Output(BaseModel):
    doubled: int


class _DoubleTool(Tool[_Input, _Output]):
    name = "double"
    description = "Doubles the given value."
    input_model = _Input
    output_model = _Output

    async def execute(self, tool_input: _Input) -> _Output:
        return _Output(doubled=tool_input.value * 2)


class _TripleTool(Tool[_Input, _Output]):
    name = "triple"
    description = "Triples the given value."
    input_model = _Input
    output_model = _Output

    async def execute(self, tool_input: _Input) -> _Output:
        return _Output(doubled=tool_input.value * 3)


def test_register_and_get_round_trips_by_name() -> None:
    registry = ToolRegistry()
    tool = _DoubleTool()

    registry.register(tool)

    assert registry.get("double") is tool


def test_get_raises_tool_not_found_error_for_an_unregistered_name() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("does-not-exist")


def test_register_is_idempotent_and_overwrites_by_name() -> None:
    registry = ToolRegistry()
    first = _DoubleTool()
    second = _DoubleTool()

    registry.register(first)
    registry.register(second)

    assert registry.get("double") is second
    assert len(registry.list_tools()) == 1


def test_list_tools_returns_every_registered_tool() -> None:
    registry = ToolRegistry()
    registry.register(_DoubleTool())
    registry.register(_TripleTool())

    names = {tool.name for tool in registry.list_tools()}

    assert names == {"double", "triple"}


def test_list_metadata_returns_every_tools_self_description() -> None:
    registry = ToolRegistry()
    registry.register(_DoubleTool())
    registry.register(_TripleTool())

    metadata = registry.list_metadata()

    names = {entry["name"] for entry in metadata}
    assert names == {"double", "triple"}
    assert all("input_schema" in entry and "output_schema" in entry for entry in metadata)


def test_registry_never_hardcodes_which_tools_exist() -> None:
    """An empty registry has no tools until something registers one — no built-in list."""
    registry = ToolRegistry()
    assert registry.list_tools() == []
    assert registry.list_metadata() == []


def test_a_registered_tool_is_actually_invokable_through_the_registry() -> None:
    async def scenario() -> None:
        registry = ToolRegistry()
        registry.register(_DoubleTool())

        tool = registry.get("double")
        result = await tool.execute(_Input(value=21))

        assert result.doubled == 42

    asyncio.run(scenario())
