"""Exceptions raised by :class:`frontend.api.client.APIClient`.

Deliberately independent of ``backend.core.exceptions`` — the frontend
never imports backend code (see ``frontend/api/client.py`` module
docstring). ``APIError``'s fields mirror the backend's ``ErrorDetail``
shape by convention, not by shared inheritance.
"""

from typing import Any


class APIClientError(Exception):
    """Base class for every error raised by the API client."""


class BackendUnavailableError(APIClientError):
    """Raised when the backend could not be reached at all.

    Covers connection refused, DNS failure, and timeouts — anything where
    no HTTP response was ever received, as opposed to :class:`APIError`,
    which represents a response the backend did send.
    """


class APIError(APIClientError):
    """Raised when the backend responded with the unified error envelope."""

    def __init__(self, message: str, status_code: int, error_type: str, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.detail = detail
