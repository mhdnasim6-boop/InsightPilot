"""Realtime layer exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module
(``backend.workflows.exceptions``/``backend.security.exceptions``).
"""

from backend.core.exceptions import InsightPilotError


class RealtimeError(InsightPilotError):
    """Base class for every realtime-layer exception."""

    status_code = 500
    error_type = "RealtimeError"


class UnknownEventTypeError(RealtimeError):
    """Raised when a subscribe/replay request names an unrecognized EventType."""

    status_code = 422
    error_type = "UnknownEventTypeError"


class InvalidReplayRequestError(RealtimeError):
    """Raised when a replay request's own parameters are contradictory or malformed."""

    status_code = 422
    error_type = "InvalidReplayRequestError"


class UnknownSubscriptionError(RealtimeError):
    """Raised when an operation names a connection_id with no active subscription."""

    status_code = 404
    error_type = "UnknownSubscriptionError"


class WebSocketAuthenticationError(RealtimeError):
    """Raised when a WebSocket handshake presents no/invalid credentials."""

    status_code = 401
    error_type = "WebSocketAuthenticationError"
