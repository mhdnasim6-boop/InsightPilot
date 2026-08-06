"""Tests for TracingTool: the transparent Tool decorator that records a
ToolTrace for every call, correlating via the observability contextvars.
"""

import asyncio

import pytest
from pydantic import BaseModel

from backend.observability.context import agent_context, trace_context
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.services.tracing_tool import TracingTool
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.tools.base.tool import Tool


class _DummyInput(BaseModel):
    value: str


class _DummyOutput(BaseModel):
    result: str


class _DummyTool(Tool[_DummyInput, _DummyOutput]):
    name = "dummy_tool"
    description = "A tool that echoes its input, or fails on demand."
    input_model = _DummyInput
    output_model = _DummyOutput

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls = 0

    async def execute(self, tool_input: _DummyInput) -> _DummyOutput:
        self.calls += 1
        if self._fail:
            raise RuntimeError("dummy tool failure")
        return _DummyOutput(result=tool_input.value.upper())


def test_tracing_tool_proxies_identity_and_schemas() -> None:
    inner = _DummyTool()
    tool = TracingTool(inner)

    assert tool.name == "dummy_tool"
    assert tool.description == inner.description
    assert tool.input_model is _DummyInput
    assert tool.output_model is _DummyOutput
    assert tool.input_schema() == inner.input_schema()
    assert tool.output_schema() == inner.output_schema()


def test_tracing_tool_without_observability_service_just_delegates() -> None:
    async def scenario() -> None:
        inner = _DummyTool()
        tool = TracingTool(inner)

        result = await tool.execute(_DummyInput(value="hi"))

        assert result.result == "HI"
        assert inner.calls == 1

    asyncio.run(scenario())


def test_tracing_tool_outside_a_trace_context_does_not_record() -> None:
    async def scenario() -> None:
        service = ObservabilityService(TraceStore())
        tool = TracingTool(_DummyTool(), service)

        result = await tool.execute(_DummyInput(value="hi"))

        assert result.result == "HI"
        assert service.list_traces() == []

    asyncio.run(scenario())


def test_tracing_tool_records_a_completed_tool_trace_inside_a_trace_context() -> None:
    async def scenario() -> None:
        service = ObservabilityService(TraceStore())
        trace_id = service.start_trace("plan-1")
        tool = TracingTool(_DummyTool(), service)

        with trace_context(trace_id), agent_context("sql_agent"):
            await tool.execute(_DummyInput(value="hi"))

        trace = service.get_trace(trace_id)
        assert len(trace.tool_traces) == 1
        recorded = trace.tool_traces[0]
        assert recorded.tool_name == "dummy_tool"
        assert recorded.agent_name == "sql_agent"
        assert recorded.status == ExecutionStatus.COMPLETED
        assert recorded.error is None

    asyncio.run(scenario())


def test_tracing_tool_records_a_failed_tool_trace_and_reraises() -> None:
    async def scenario() -> None:
        service = ObservabilityService(TraceStore())
        trace_id = service.start_trace("plan-1")
        tool = TracingTool(_DummyTool(fail=True), service)

        with trace_context(trace_id), pytest.raises(RuntimeError, match="dummy tool failure"):
            await tool.execute(_DummyInput(value="hi"))

        trace = service.get_trace(trace_id)
        assert len(trace.tool_traces) == 1
        recorded = trace.tool_traces[0]
        assert recorded.status == ExecutionStatus.FAILED
        assert recorded.error == "dummy tool failure"

    asyncio.run(scenario())


def test_tracing_tool_finalized_trace_reflects_recorded_calls() -> None:
    async def scenario() -> None:
        service = ObservabilityService(TraceStore())
        trace_id = service.start_trace("plan-1")
        tool = TracingTool(_DummyTool(), service)

        with trace_context(trace_id):
            await tool.execute(_DummyInput(value="hi"))

        finalized = service.finalize_trace(trace_id, PlanStatus.COMPLETED)
        assert len(finalized.tool_traces) == 1

    asyncio.run(scenario())
