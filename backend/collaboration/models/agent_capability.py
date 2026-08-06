"""AgentCapability: one agent's self-description for dynamic discovery.

Replaces PlannerAgent's own hardcoded/direct ``GraphBuilder.export()``
read on the direct-REST invocation path: ``name``/``description``/
``accepted_inputs`` are still sourced from each ``OrchestrationNode.metadata()``
(reused, never re-typed), while ``produced_outputs``/``supported_tools``/
``estimated_cost``/``estimated_duration`` are genuinely new metadata this
phase introduces — see ``backend.collaboration.coordinator.capability_registry``.
"""

from pydantic import BaseModel, ConfigDict, Field


class AgentCapability(BaseModel):
    """One agent's declared inputs, outputs, tools, and rough cost/duration."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    accepted_inputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)
    supported_tools: list[str] = Field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_duration: float = 0.0
