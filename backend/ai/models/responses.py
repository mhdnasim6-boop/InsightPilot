"""Provider-independent response and streaming-chunk models."""

from typing import Any

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token accounting for a single request/response."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class AIResponse(BaseModel):
    """The result of a single, non-streamed AI generation."""

    content: str
    model: str
    provider: str
    usage: TokenUsage
    finish_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamingChunk(BaseModel):
    """A single piece of a streamed AI generation."""

    delta: str
    index: int = Field(ge=0)
    is_final: bool = False
    finish_reason: str | None = None
