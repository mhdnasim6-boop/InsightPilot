"""MCPToolResult: the structured response MCPService always returns for a tool invocation.

A uniform envelope regardless of which server/transport handled the
call — callers never branch on transport-specific response shapes.
"""

from typing import Any

from pydantic import BaseModel


class MCPToolResult(BaseModel):
    """The outcome of one MCPClient.invoke() call."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
