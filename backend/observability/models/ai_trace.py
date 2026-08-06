"""AICallTrace: one AIService.generate() call's recorded execution.

``tokens`` reuses ``TokenUsage`` directly from
``backend.ai.models.responses`` — never redefined — the same reuse
relationship every agent result has with its own domain models.
``estimated_cost`` is a best-effort, clearly-labeled per-provider/
per-model cost estimate (see ``backend.observability.services.cost``);
it is observability infrastructure (a derived number attached to a
trace), not new business logic.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.ai.models.responses import TokenUsage


class AICallTrace(BaseModel):
    """One AI provider call's recorded execution within a trace."""

    model_config = ConfigDict(frozen=True)

    agent_name: str | None = None
    provider: str
    model: str
    tokens: TokenUsage
    start_time: datetime
    end_time: datetime
    latency_ms: float
    estimated_cost: float
    temperature: float | None = None
