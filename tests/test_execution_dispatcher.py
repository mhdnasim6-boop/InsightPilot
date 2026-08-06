"""Tests for NodeDispatcher: dict-based dispatch by node_name, no if/else chains."""

import asyncio

import pytest
from pydantic import BaseModel

from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.exceptions.errors import UnknownNodeError
from backend.planning.models.step import ExecutionStep


class _Result(BaseModel):
    step_id: str


class _StubService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        self.calls.append(step.step_id)
        return _Result(step_id=step.step_id)


def test_register_and_dispatch_routes_to_the_correct_service() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        file_service = _StubService()
        sql_service = _StubService()
        dispatcher.register("file_agent", file_service)
        dispatcher.register("sql_agent", sql_service)

        step = ExecutionStep(step_id="s1", name="File", node_name="file_agent")
        result = await dispatcher.dispatch(step, "session-1")

        assert result.step_id == "s1"
        assert file_service.calls == ["s1"]
        assert sql_service.calls == []

    asyncio.run(scenario())


def test_dispatch_raises_unknown_node_error_for_an_unregistered_node_name() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        step = ExecutionStep(step_id="s1", name="Ghost", node_name="not_registered")

        with pytest.raises(UnknownNodeError):
            await dispatcher.dispatch(step, None)

    asyncio.run(scenario())


def test_is_registered_and_registered_node_names() -> None:
    dispatcher = NodeDispatcher()
    dispatcher.register("file_agent", _StubService())
    dispatcher.register("sql_agent", _StubService())

    assert dispatcher.is_registered("file_agent") is True
    assert dispatcher.is_registered("browser_agent") is False
    assert dispatcher.registered_node_names() == ["file_agent", "sql_agent"]


def test_register_overwrites_an_existing_registration() -> None:
    async def scenario() -> None:
        dispatcher = NodeDispatcher()
        first = _StubService()
        second = _StubService()
        dispatcher.register("file_agent", first)
        dispatcher.register("file_agent", second)

        step = ExecutionStep(step_id="s1", name="File", node_name="file_agent")
        await dispatcher.dispatch(step, None)

        assert first.calls == []
        assert second.calls == ["s1"]

    asyncio.run(scenario())
