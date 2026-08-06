"""MCP endpoints: register/list/remove servers, aggregate health, recognized capabilities.

Thin HTTP wrappers over the existing ``MCPService`` — no registration or
routing logic here. Connection/tool-invocation are deliberately not
exposed over HTTP this phase (no real MCPClient exists to route to yet);
only registry-level bookkeeping is, matching this phase's explicit scope.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.mcp import get_mcp_service
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.health_summary import MCPHealthSummary
from backend.mcp.models.server import MCPServerDefinition
from backend.mcp.services.mcp_service import MCPService
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/mcp")


@router.post("/servers", response_model=SuccessResponse[MCPServerDefinition], summary="Register an MCP server")
async def register_server(
    definition: MCPServerDefinition, mcp_service: MCPService = Depends(get_mcp_service)
) -> SuccessResponse[MCPServerDefinition]:
    """Register a new MCP server. Raises MCPServerAlreadyRegisteredError (409) if the id is taken."""
    registered = mcp_service.register_server(definition)
    return SuccessResponse.ok(data=registered, message=f"Server '{registered.server_id}' registered.")


@router.get("/servers", response_model=SuccessResponse[list[MCPServerDefinition]], summary="List registered MCP servers")
async def list_servers(mcp_service: MCPService = Depends(get_mcp_service)) -> SuccessResponse[list[MCPServerDefinition]]:
    """Return every registered MCP server."""
    return SuccessResponse.ok(data=mcp_service.list_servers(), message="MCP servers fetched.")


@router.get("/health", response_model=SuccessResponse[MCPHealthSummary], summary="Aggregate MCP server health")
async def get_mcp_health(mcp_service: MCPService = Depends(get_mcp_service)) -> SuccessResponse[MCPHealthSummary]:
    """Aggregate how many registered servers are in each lifecycle state."""
    return SuccessResponse.ok(data=mcp_service.health_summary(), message="MCP health summary fetched.")


@router.get("/capabilities", response_model=SuccessResponse[list[MCPCapability]], summary="List recognized MCP capabilities")
async def get_mcp_capabilities() -> SuccessResponse[list[MCPCapability]]:
    """List every capability kind the MCP layer recognizes (implemented or not)."""
    return SuccessResponse.ok(data=list(MCPCapability), message="MCP capabilities fetched.")


@router.get("/servers/{server_id}", response_model=SuccessResponse[MCPServerDefinition], summary="Fetch one MCP server")
async def get_server(
    server_id: str, mcp_service: MCPService = Depends(get_mcp_service)
) -> SuccessResponse[MCPServerDefinition]:
    """Fetch a single registered server by id. Raises MCPServerNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=mcp_service.get_server(server_id), message="MCP server fetched.")


@router.delete("/servers/{server_id}", response_model=SuccessResponse[MCPServerDefinition], summary="Remove an MCP server")
async def remove_server(
    server_id: str, mcp_service: MCPService = Depends(get_mcp_service)
) -> SuccessResponse[MCPServerDefinition]:
    """Unregister a server. Raises MCPServerNotFoundError (404) if unknown. Returns the removed definition."""
    definition = mcp_service.get_server(server_id)
    mcp_service.unregister_server(server_id)
    return SuccessResponse.ok(data=definition, message=f"Server '{server_id}' removed.")
