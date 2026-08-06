"""Aggregate registry-wide health, for the /mcp/health endpoint and MCP page."""

from pydantic import BaseModel, Field, model_validator

from backend.mcp.lifecycle.status import MCPConnectionStatus


class MCPHealthSummary(BaseModel):
    """How many registered servers are in each lifecycle state.

    ``by_status`` is keyed by the plain string value (not the enum
    itself) purely so it serializes as a normal JSON object with no
    ambiguity about enum-key encoding.
    """

    total_servers: int
    by_status: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_missing_statuses(self) -> "MCPHealthSummary":
        for status in MCPConnectionStatus:
            self.by_status.setdefault(status.value, 0)
        return self
