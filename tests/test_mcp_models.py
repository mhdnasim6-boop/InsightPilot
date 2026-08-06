"""Tests for MCP models: MCPServerDefinition, MCPCapability, MCPHealthSummary."""

import json

from backend.mcp.lifecycle.status import MCPConnectionStatus
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.health_summary import MCPHealthSummary
from backend.mcp.models.server import MCPServerDefinition
from backend.mcp.transport.transport_type import MCPTransportType


def test_server_definition_defaults_status_to_disconnected() -> None:
    definition = MCPServerDefinition(server_id="fs-1", name="Local Filesystem", transport=MCPTransportType.STDIO)
    assert definition.status == MCPConnectionStatus.DISCONNECTED
    assert definition.version == "1.0.0"
    assert definition.capabilities == []
    assert definition.description is None


def test_server_definition_accepts_multiple_capabilities() -> None:
    definition = MCPServerDefinition(
        server_id="fs-1",
        name="Local Filesystem",
        transport=MCPTransportType.STDIO,
        capabilities=[MCPCapability.FILESYSTEM, MCPCapability.PYTHON],
    )
    assert definition.capabilities == [MCPCapability.FILESYSTEM, MCPCapability.PYTHON]


def test_server_definition_round_trips_through_json() -> None:
    definition = MCPServerDefinition(
        server_id="sql-1",
        name="SQL Bridge",
        description="Read-only SQL access",
        transport=MCPTransportType.HTTP,
        status=MCPConnectionStatus.CONNECTED,
        capabilities=[MCPCapability.SQL],
        version="2.1.0",
        metadata={"url": "https://example.internal/mcp"},
    )

    restored = MCPServerDefinition.model_validate(json.loads(definition.model_dump_json()))

    assert restored == definition


def test_capability_enum_has_all_six_recognized_values() -> None:
    assert {c.value for c in MCPCapability} == {"filesystem", "python", "browser", "sql", "git", "custom"}


def test_transport_type_enum_has_all_three_recognized_values() -> None:
    assert {t.value for t in MCPTransportType} == {"stdio", "http", "websocket"}


def test_health_summary_fills_in_every_status_with_zero_by_default() -> None:
    summary = MCPHealthSummary(total_servers=0)
    assert summary.by_status == {
        "disconnected": 0,
        "starting": 0,
        "connected": 0,
        "stopping": 0,
        "failed": 0,
    }


def test_health_summary_preserves_given_counts_and_fills_the_rest() -> None:
    summary = MCPHealthSummary(total_servers=3, by_status={"connected": 2, "failed": 1})
    assert summary.by_status["connected"] == 2
    assert summary.by_status["failed"] == 1
    assert summary.by_status["disconnected"] == 0
    assert summary.total_servers == 3
