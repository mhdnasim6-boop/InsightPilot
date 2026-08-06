"""Request model for POST /api/v1/chat."""

from pydantic import BaseModel

from backend.chatbot.context.models import ChatContext


class ChatRequest(BaseModel):
    """One chat turn: the user's question plus the full context to answer it from."""

    question: str
    context: ChatContext
