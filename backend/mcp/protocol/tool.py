"""MCPTool: one tool a server exposes, as returned by MCPClient.list_tools()."""

from typing import Any

from pydantic import BaseModel, Field


class MCPTool(BaseModel):
    """A single callable a server advertises — name, description, and its argument shape."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
