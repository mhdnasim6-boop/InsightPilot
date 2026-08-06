"""Tool: the abstract contract every Tool Layer wrapper must satisfy.

Every existing agent (File/SQL/Browser/Report/ExecutiveSummary) already
calls exactly one backend service per concern, each wrapped in the
agent's own try/except. The Tool Layer makes that one-call-per-concern
boundary an explicit, self-describing object instead of an implicit
convention — mirroring ``OrchestrationNode.metadata()``'s own
self-description precedent from the real Planner Agent (Phase 21), one
layer further down. ``execute()`` itself still only calls the one
wrapped service and returns (or raises) exactly as the agent's own
inline code did before this phase: a Tool adds no new error-handling
convention, no swallowed exceptions — the calling agent's own try/except
remains the sole error boundary.

``input_schema()``/``output_schema()`` return JSON Schema (via pydantic's
own ``model_json_schema()``) — deliberately the same shape an MCP tool
declaration exposes, so a future ``MCPToolAdapter`` implementing this
same contract is a drop-in registry entry, not a parallel abstraction.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Tool(ABC, Generic[InputT, OutputT]):
    """Contract every tool (today: a service wrapper; tomorrow: possibly an MCP-backed proxy) must satisfy."""

    name: str
    description: str
    input_model: type[InputT]
    output_model: type[OutputT]

    @abstractmethod
    async def execute(self, tool_input: InputT) -> OutputT:
        """Run this tool's one wrapped service call and return its result.

        Raises whatever the wrapped service itself raises for a genuine
        failure — a Tool never catches/swallows an exception itself.
        """

    def input_schema(self) -> dict[str, Any]:
        """JSON schema for this tool's input."""
        return self.input_model.model_json_schema()

    def output_schema(self) -> dict[str, Any]:
        """JSON schema for this tool's output."""
        return self.output_model.model_json_schema()

    def metadata(self) -> dict[str, Any]:
        """Self-description for registry/introspection use — mirrors OrchestrationNode.metadata()."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
            "output_schema": self.output_schema(),
        }
