"""Tests for MCPServerRegistry: register/unregister/lookup/list/status/health."""

import pytest

from backend.mcp.exceptions.errors import (
    InvalidLifecycleTransitionError,
    MCPServerAlreadyRegisteredError,
    MCPServerNotFoundError,
)
from backend.mcp.lifecycle.status import MCPConnectionStatus
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.server import MCPServerDefinition
from backend.mcp.registry.server_registry import MCPServerRegistry
from backend.mcp.transport.transport_type import MCPTransportType


def _definition(server_id: str = "fs-1", **overrides: object) -> MCPServerDefinition:
    fields: dict[str, object] = {
        "server_id": server_id,
        "name": "Local Filesystem",
        "transport": MCPTransportType.STDIO,
        "capabilities": [MCPCapability.FILESYSTEM],
    }
    fields.update(overrides)
    return MCPServerDefinition.model_validate(fields)


def test_register_then_get_returns_the_same_definition() -> None:
    registry = MCPServerRegistry()
    definition = _definition()

    registry.register(definition)

    assert registry.get("fs-1") == definition


def test_register_twice_with_the_same_id_raises() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition())

    with pytest.raises(MCPServerAlreadyRegisteredError):
        registry.register(_definition())


def test_get_unknown_server_raises_not_found() -> None:
    registry = MCPServerRegistry()
    with pytest.raises(MCPServerNotFoundError):
        registry.get("does-not-exist")


def test_unregister_removes_a_server_and_returns_true() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition())

    assert registry.unregister("fs-1") is True
    with pytest.raises(MCPServerNotFoundError):
        registry.get("fs-1")


def test_unregister_unknown_server_returns_false() -> None:
    registry = MCPServerRegistry()
    assert registry.unregister("does-not-exist") is False


def test_unregister_then_register_again_succeeds() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition())
    registry.unregister("fs-1")

    registry.register(_definition(name="Local Filesystem v2"))

    assert registry.get("fs-1").name == "Local Filesystem v2"


def test_list_returns_every_registered_server() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition("fs-1"))
    registry.register(_definition("sql-1", capabilities=[MCPCapability.SQL]))

    servers = registry.list()

    assert {s.server_id for s in servers} == {"fs-1", "sql-1"}


def test_list_by_capability_filters_correctly() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition("fs-1", capabilities=[MCPCapability.FILESYSTEM]))
    registry.register(_definition("sql-1", capabilities=[MCPCapability.SQL]))
    registry.register(_definition("multi-1", capabilities=[MCPCapability.SQL, MCPCapability.PYTHON]))

    sql_servers = registry.list_by_capability(MCPCapability.SQL)

    assert {s.server_id for s in sql_servers} == {"sql-1", "multi-1"}


def test_update_status_applies_a_valid_transition() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition())

    updated = registry.update_status("fs-1", MCPConnectionStatus.STARTING)

    assert updated.status == MCPConnectionStatus.STARTING
    assert registry.get("fs-1").status == MCPConnectionStatus.STARTING


def test_update_status_rejects_an_invalid_transition() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition())  # starts DISCONNECTED

    with pytest.raises(InvalidLifecycleTransitionError):
        registry.update_status("fs-1", MCPConnectionStatus.CONNECTED)  # skips STARTING

    assert registry.get("fs-1").status == MCPConnectionStatus.DISCONNECTED  # unchanged


def test_update_status_unknown_server_raises_not_found() -> None:
    registry = MCPServerRegistry()
    with pytest.raises(MCPServerNotFoundError):
        registry.update_status("does-not-exist", MCPConnectionStatus.STARTING)


def test_health_summary_counts_every_status_across_registered_servers() -> None:
    registry = MCPServerRegistry()
    registry.register(_definition("fs-1"))
    registry.register(_definition("sql-1"))
    registry.register(_definition("git-1"))
    registry.update_status("fs-1", MCPConnectionStatus.STARTING)
    registry.update_status("sql-1", MCPConnectionStatus.STARTING)
    registry.update_status("sql-1", MCPConnectionStatus.CONNECTED)

    summary = registry.health_summary()

    assert summary.total_servers == 3
    assert summary.by_status["connected"] == 1
    assert summary.by_status["starting"] == 1
    assert summary.by_status["disconnected"] == 1
    assert summary.by_status["failed"] == 0


def test_health_summary_on_an_empty_registry() -> None:
    registry = MCPServerRegistry()
    summary = registry.health_summary()
    assert summary.total_servers == 0
    assert summary.by_status == {"disconnected": 0, "starting": 0, "connected": 0, "stopping": 0, "failed": 0}
