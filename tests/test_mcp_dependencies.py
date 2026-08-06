"""Tests for backend.dependencies.mcp: singleton caching and wiring.

Provider functions with a Depends(...)-defaulted parameter only resolve
correctly through FastAPI's own request handling (confirmed empirically:
calling get_mcp_service() bare binds ``registry`` to the literal
``Depends`` marker object, not a real MCPServerRegistry, and only fails
once something tries to use it) — so every call here passes the
dependency explicitly instead of relying on that resolution.
"""

from collections.abc import Iterator

import pytest

from backend.dependencies.mcp import get_mcp_server_registry, get_mcp_service
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.server import MCPServerDefinition
from backend.mcp.registry.server_registry import MCPServerRegistry
from backend.mcp.services.mcp_service import MCPService
from backend.mcp.transport.transport_type import MCPTransportType


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    get_mcp_server_registry.cache_clear()
    get_mcp_service.cache_clear()
    yield
    get_mcp_server_registry.cache_clear()
    get_mcp_service.cache_clear()


def test_get_mcp_server_registry_is_a_singleton() -> None:
    assert get_mcp_server_registry() is get_mcp_server_registry()


def test_get_mcp_server_registry_returns_the_real_type() -> None:
    assert isinstance(get_mcp_server_registry(), MCPServerRegistry)


def test_get_mcp_service_is_a_singleton_given_the_same_registry() -> None:
    registry = get_mcp_server_registry()
    assert get_mcp_service(registry) is get_mcp_service(registry)


def test_get_mcp_service_returns_the_real_type() -> None:
    registry = get_mcp_server_registry()
    assert isinstance(get_mcp_service(registry), MCPService)


def test_get_mcp_service_is_wired_to_the_singleton_registry() -> None:
    """A server registered through the cached service must be visible
    through the cached registry singleton directly — proving they share
    state rather than each being freshly constructed."""
    registry = get_mcp_server_registry()
    service = get_mcp_service(registry)

    definition = MCPServerDefinition(
        server_id="fs-1", name="Local Filesystem", transport=MCPTransportType.STDIO,
        capabilities=[MCPCapability.FILESYSTEM],
    )
    service.register_server(definition)

    assert registry.get("fs-1") == definition
    assert registry.list() == [definition]
