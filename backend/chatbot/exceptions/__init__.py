"""Chatbot exception hierarchy."""

from backend.chatbot.exceptions.errors import ChatError, UnknownIntentError

__all__ = ["ChatError", "UnknownIntentError"]
