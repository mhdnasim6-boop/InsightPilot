"""Chatbot exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
chatbot-specific special-casing.

Note what is deliberately *not* here: there is no "couldn't answer the
question" exception. A question the assistant lacks data for is a normal,
expected outcome — modeled as a ``ChatResponse`` with ``answerable=False``,
exactly like ``AnalysisSectionResult.applicable=False`` is data, not an
error, elsewhere in this codebase. These exceptions exist only for
genuinely exceptional/programmer-error conditions.
"""

from backend.core.exceptions import InsightPilotError


class ChatError(InsightPilotError):
    """Base class for all chatbot exceptions."""

    status_code = 500
    error_type = "ChatError"


class UnknownIntentError(ChatError):
    """Raised when a classified intent has no registered prompt category.

    Should never happen in practice — ``Intent`` is a closed enum and
    every member is registered by :func:`register_chat_prompts` — this
    exists as a defensive guard against the two drifting apart.
    """

    status_code = 500
    error_type = "UnknownIntentError"
