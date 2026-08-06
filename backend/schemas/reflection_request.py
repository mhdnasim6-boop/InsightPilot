"""Request body for POST /reflection/generate.

Mirrors ``ExecutionStartRequest``'s own shape: carries the real
``ExecutionPlan`` directly (never just a plan_id) — the REST handler
fetches everything else (``ExecutionTrace`` via ``ObservabilityService``,
an optional ``CollaborationTask``/``ReportDocument`` via
``CollaborationService``/``ReportService``) using the ids given here.
"""

from pydantic import BaseModel

from backend.planning.models.plan import ExecutionPlan


class ReflectionGenerateRequest(BaseModel):
    """What to reflect on: a completed plan, plus optional collaboration/report context."""

    plan: ExecutionPlan
    collaboration_id: str | None = None
    report_id: str | None = None
