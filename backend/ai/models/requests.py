"""Provider-independent request model."""

from typing import Any

from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    """The only request shape any caller builds — never a provider SDK's own type."""

    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
