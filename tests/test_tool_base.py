"""Unit tests for the Tool abstract base class's contract.

Uses one small, local concrete tool — not any real production tool —
to test the ABC's own behavior (schema generation, metadata shape) in
isolation from any real service.
"""

import asyncio

from pydantic import BaseModel

from backend.tools.base.tool import Tool


class _EchoInput(BaseModel):
    message: str


class _EchoOutput(BaseModel):
    echoed: str


class _EchoTool(Tool[_EchoInput, _EchoOutput]):
    name = "echo"
    description = "Echoes the given message back."
    input_model = _EchoInput
    output_model = _EchoOutput

    async def execute(self, tool_input: _EchoInput) -> _EchoOutput:
        return _EchoOutput(echoed=tool_input.message)


def test_execute_runs_and_returns_the_output_model() -> None:
    async def scenario() -> None:
        tool = _EchoTool()
        result = await tool.execute(_EchoInput(message="hello"))
        assert result.echoed == "hello"

    asyncio.run(scenario())


def test_input_schema_matches_the_input_model_json_schema() -> None:
    tool = _EchoTool()
    assert tool.input_schema() == _EchoInput.model_json_schema()
    assert "message" in tool.input_schema()["properties"]


def test_output_schema_matches_the_output_model_json_schema() -> None:
    tool = _EchoTool()
    assert tool.output_schema() == _EchoOutput.model_json_schema()
    assert "echoed" in tool.output_schema()["properties"]


def test_metadata_carries_name_description_and_both_schemas() -> None:
    tool = _EchoTool()
    metadata = tool.metadata()

    assert metadata["name"] == "echo"
    assert metadata["description"] == "Echoes the given message back."
    assert metadata["input_schema"] == tool.input_schema()
    assert metadata["output_schema"] == tool.output_schema()


def test_a_failing_tool_raises_rather_than_swallowing_the_exception() -> None:
    class _BoomTool(Tool[_EchoInput, _EchoOutput]):
        name = "boom"
        description = "Always fails."
        input_model = _EchoInput
        output_model = _EchoOutput

        async def execute(self, tool_input: _EchoInput) -> _EchoOutput:
            raise RuntimeError("simulated failure")

    async def scenario() -> None:
        tool = _BoomTool()
        try:
            await tool.execute(_EchoInput(message="x"))
        except RuntimeError as exc:
            assert "simulated failure" in str(exc)
        else:
            raise AssertionError("expected RuntimeError to propagate")

    asyncio.run(scenario())
