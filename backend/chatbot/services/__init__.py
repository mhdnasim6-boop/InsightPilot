"""The conversational BI service — the only public entry point of ``backend.chatbot``."""

from backend.chatbot.services.chat_service import ChatService

__all__ = ["ChatService"]
