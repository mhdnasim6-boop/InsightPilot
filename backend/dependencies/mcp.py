"""MCP providers: server registry, MCP service."""

from functools import lru_cache

from fastapi import Depends

from backend.mcp.registry.server_registry import MCPServerRegistry
from backend.mcp.services.mcp_service import MCPService


@lru_cache
def get_mcp_server_registry() -> MCPServerRegistry:
    """Return the process-wide MCPServerRegistry singleton.

    Cached for the same reason as ``get_business_dataset_store``/
    ``get_report_store``: a server registered by one request must still
    be listable in a later one.
    """
    return MCPServerRegistry()


@lru_cache
def get_mcp_service(registry: MCPServerRegistry = Depends(get_mcp_server_registry)) -> MCPService:
    """Return the process-wide MCPService singleton.

    Cached like ``get_execution_engine``: MCPService itself holds
    mutable state (which MCPClient is attached to which server) that
    must survive across requests, not just the registry it wraps.
    """
    return MCPService(registry)
