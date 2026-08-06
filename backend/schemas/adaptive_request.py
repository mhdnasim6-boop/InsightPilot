"""Request body for POST /adaptive/optimize and POST /adaptive/explain.

Mirrors ``ReflectionGenerateRequest``'s own shape: carries the real
``ExecutionPlan`` directly, never just a plan_id.
"""

from pydantic import BaseModel

from backend.planning.models.plan import ExecutionPlan


class AdaptiveOptimizeRequest(BaseModel):
    """A plan to optimize (or explain) against historical evidence."""

    plan: ExecutionPlan
    session_id: str | None = None
