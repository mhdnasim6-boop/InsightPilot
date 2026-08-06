"""PlannerInput/PlannerOutput: the Planner Agent's only public input/output shapes."""

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.planner.models.complexity import ComplexityLevel
from backend.ingestion.models.dataset import BusinessDataset
from backend.planning.models.plan import ExecutionPlan


class PlannerInput(BaseModel):
    """Everything the Planner needs to understand a request and produce a plan.

    ``available_services`` is how the caller tells the Planner what can
    actually be referenced in a step's ``node_name`` — e.g. the node names
    from ``OrchestrationService.get_graph_metadata()``. The Planner itself
    never queries orchestration directly; it only validates against
    whatever set the caller declares. ``available_service_descriptions``
    is a parallel, purely-informational name -> description mapping (also
    caller-declared, typically sourced from each node's own
    ``metadata()``) used only to enrich the prompt — validation always
    goes through ``available_services`` alone.

    ``available_sql_connections``, ``available_browser_context``, and
    ``existing_reports`` are simple caller-supplied hints (e.g. connection
    labels, prior search topics, report titles) — not new registries.
    They let the Planner reason about what's already available without
    this package owning any new business logic to track it.
    """

    user_request: str
    session_id: str | None = None
    conversation_summary: str | None = None
    uploaded_datasets: list[BusinessDataset] = Field(default_factory=list)
    available_services: list[str] = Field(default_factory=list)
    available_service_descriptions: dict[str, str] = Field(default_factory=dict)
    available_sql_connections: list[str] = Field(default_factory=list)
    available_browser_context: list[str] = Field(default_factory=list)
    existing_reports: list[str] = Field(default_factory=list)
    user_preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    """The Planner's complete answer to one ``PlannerInput`` — never anything executed."""

    goal: str
    reasoning_summary: str
    execution_plan: ExecutionPlan
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    estimated_complexity: ComplexityLevel
    estimated_duration: float | None = None
