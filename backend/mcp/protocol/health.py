"""MCPHealthStatus: a live health-check result from one server's own MCPClient.

Distinct from ``backend.mcp.models.health_summary.MCPHealthSummary``:
this is one server's real-time answer to "are you OK right now" (a
protocol-level exchange with a live client); the summary is the
registry's own bookkeeping aggregate across every registered server.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.mcp.lifecycle.status import MCPConnectionStatus
from backend.utils.time import utc_now


class MCPHealthStatus(BaseModel):
    """One server's health, as reported by its own MCPClient.health() call."""

    server_id: str
    status: MCPConnectionStatus
    message: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)
