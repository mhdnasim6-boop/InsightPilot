"""Provider-independent provider/model metadata models."""

from datetime import datetime

from pydantic import BaseModel


class ModelInfo(BaseModel):
    """Describes a specific model exposed by a provider."""

    name: str
    provider: str
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    supports_streaming: bool = False


class ProviderHealth(BaseModel):
    """Result of a single provider health check."""

    provider: str
    healthy: bool
    message: str = ""
    checked_at: datetime
