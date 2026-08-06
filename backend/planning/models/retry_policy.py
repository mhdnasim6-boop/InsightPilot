"""Per-step retry configuration."""

from pydantic import BaseModel, Field


class StepRetryPolicy(BaseModel):
    """Retry behavior for a single execution step."""

    max_attempts: int = Field(default=1, ge=1)
    backoff_seconds: float = Field(default=0.0, ge=0.0)
