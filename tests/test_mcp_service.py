"""Tests for MCPService: registry management, connection management, and tool
routing — exercised through a test-local fake MCPClient, the same way
test_chatbot_service.py uses a test-local fake AIService wrapper. No real
MCP client implementation exists anywhere in backend/mcp/ itself.
"""

import asyncio
from typing import Any

import pytest

from backend.mcp.client.base import MCPClient
from backend.mcp.exceptions.errors import (
    MCPClientNotAvailableError,
    MCPConnectionFailedError,
    MCPServerNotConnectedError,
    MCPServerNotFoundError,
)
from backend.mcp.lifecycle.status import MCPConnectionStatus
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.server import MCPServerDefinition
from backend.mcp.protocol.health import MCPHealthStatus
from backend.mcp.protocol.result import MCPToolResult
from backend.mcp.protocol.tool import MCPTool
from backend.mcp.registry.server_registry import MCPServerRegistry
from backend.mcp.services.mcp_service import MCPService
from backend.mcp.transport.transport_type import MCPTransportType


class _FakeMCPClient(MCPClient):
    """A minimal, fully in-memory MCPClient — proves MCPService's routing works
    without depending on any real transport."""

    def __init__(self, server_id: str, fail_connect: bool = False) -> None:
        self.server_id = server_id
        self._fail_connect = fail_connect
        self.connected = False
        self.disconnect_called = False

    async def connect(self) -> None:
        if self._fail_connect:
            raise RuntimeError("simulated connection failure")
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False
        self.disconnect_called = True

    async def health(self) -> MCPHealthStatus:
        status = MCPConnectionStatus.CONNECTED if self.connected else MCPConnectionStatus.DISCONNECTED
        return MCPHealthStatus(server_id=self.server_id, status=status)

    async def list_tools(self) -> list[MCPTool]:
        return [MCPTool(name="read_file", description="Read a file", parameters={"path": "string"})]

    async def invoke(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(tool_name=tool_name, success=True, result=f"invoked {tool_name} with {arguments}")


def _definition(server_id: str = "fs-1") -> MCPServerDefinition:
    return MCPServerDefinition(
        server_id=server_id, name="Local Filesystem", transport=MCPTransportType.STDIO,
        capabilities=[MCPCapability.FILESYSTEM],
    )


def _make_service() -> MCPService:
    return MCPService(MCPServerRegistry())


def test_register_server_makes_it_listable() -> None:
    service = _make_service()
    service.register_server(_definition())
    assert [s.server_id for s in service.list_servers()] == ["fs-1"]


def test_list_servers_by_capability() -> None:
    service = _make_service()
    service.register_server(_definition("fs-1"))
    service.register_server(
        MCPServerDefinition(
            server_id="sql-1", name="SQL Bridge", transport=MCPTransportType.HTTP, capabilities=[MCPCapability.SQL]
        )
    )
    assert [s.server_id for s in service.list_servers_by_capability(MCPCapability.SQL)] == ["sql-1"]


def test_attach_client_to_an_unregistered_server_raises_not_found() -> None:
    service = _make_service()
    with pytest.raises(MCPServerNotFoundError):
        service.attach_client("does-not-exist", _FakeMCPClient("does-not-exist"))


def test_connect_without_an_attached_client_raises_client_not_available() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        with pytest.raises(MCPClientNotAvailableError):
            await service.connect("fs-1")
        # status must be untouched, not left mid-transition
        assert service.get_server("fs-1").status == MCPConnectionStatus.DISCONNECTED

    asyncio.run(scenario())


def test_connect_success_moves_server_to_connected() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1"))

        updated = await service.connect("fs-1")

        assert updated.status == MCPConnectionStatus.CONNECTED

    asyncio.run(scenario())


def test_connect_failure_leaves_server_failed_and_raises() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1", fail_connect=True))

        with pytest.raises(MCPConnectionFailedError):
            await service.connect("fs-1")

        assert service.get_server("fs-1").status == MCPConnectionStatus.FAILED

    asyncio.run(scenario())


def test_disconnect_moves_a_connected_server_back_to_disconnected() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        client = _FakeMCPClient("fs-1")
        service.attach_client("fs-1", client)
        await service.connect("fs-1")

        updated = await service.disconnect("fs-1")

        assert updated.status == MCPConnectionStatus.DISCONNECTED
        assert client.disconnect_called is True

    asyncio.run(scenario())


def test_list_tools_requires_a_connected_server() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1"))

        with pytest.raises(MCPServerNotConnectedError):
            await service.list_tools("fs-1")

        await service.connect("fs-1")
        tools = await service.list_tools("fs-1")
        assert tools == [MCPTool(name="read_file", description="Read a file", parameters={"path": "string"})]

    asyncio.run(scenario())


def test_invoke_tool_routes_to_the_attached_client_and_returns_a_structured_result() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1"))
        await service.connect("fs-1")

        result = await service.invoke_tool("fs-1", "read_file", {"path": "/tmp/x"})

        assert result.success is True
        assert result.tool_name == "read_file"
        assert "read_file" in str(result.result)

    asyncio.run(scenario())


def test_invoke_tool_on_a_disconnected_server_raises_not_connected() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1"))

        with pytest.raises(MCPServerNotConnectedError):
            await service.invoke_tool("fs-1", "read_file", {})

    asyncio.run(scenario())


def test_check_health_does_not_require_a_connected_server() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1"))

        health = await service.check_health("fs-1")

        assert health.status == MCPConnectionStatus.DISCONNECTED  # honest: client was never connected

    asyncio.run(scenario())


def test_unregister_server_detaches_its_client() -> None:
    async def scenario() -> None:
        service = _make_service()
        service.register_server(_definition())
        service.attach_client("fs-1", _FakeMCPClient("fs-1"))

        assert service.unregister_server("fs-1") is True
        service.register_server(_definition())  # re-register the same id

        with pytest.raises(MCPClientNotAvailableError):
            await service.connect("fs-1")  # the old client is gone, not silently reused

    asyncio.run(scenario())


def test_health_summary_reflects_registered_servers() -> None:
    service = _make_service()
    service.register_server(_definition("fs-1"))
    service.register_server(_definition("fs-2"))

    summary = service.health_summary()

    assert summary.total_servers == 2
    assert summary.by_status["disconnected"] == 2
