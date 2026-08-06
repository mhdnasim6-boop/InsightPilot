"""The chatbot's complete, structured answer to one question."""

from typing import Any

from pydantic import BaseModel, Field

from backend.chatbot.retrieval.classifier import Intent


class ChatResponse(BaseModel):
    """Everything the frontend needs to render one answer.

    ``referenced_*`` are never parsed out of the model's own text — they
    are exactly what :class:`~backend.chatbot.retrieval.context_builder.ContextBuilder`
    decided to include in the prompt, so the assistant can never claim to
    have referenced something it wasn't actually shown.
    """

    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    intent: Intent
    answerable: bool
    referenced_kpis: list[str] = Field(default_factory=list)
    referenced_charts: list[str] = Field(default_factory=list)
    referenced_insights: list[str] = Field(default_factory=list)
    referenced_datasets: list[str] = Field(default_factory=list)
    suggested_follow_up_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
