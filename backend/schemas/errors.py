"""Consistent error response shape used by every exception handler.

Matches the project-wide unified API envelope: ``{success, message,
errors}``. Diagnostic detail that used to sit at the top level (status
code, error type, path) now lives nested under ``errors``.
"""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Structured detail about what went wrong."""

    type: str = Field(..., description="Machine-readable error type.", examples=["NotFoundError"])
    status_code: int = Field(..., description="HTTP status code.", examples=[404])
    path: str = Field(..., description="Request path that triggered the error.")
    detail: Any | None = Field(default=None, description="Additional structured error context, if any.")


class ErrorResponse(BaseModel):
    """Unified failure envelope returned by every endpoint/exception handler."""

    success: bool = Field(default=False)
    message: str = Field(..., description="Human-readable error message.")
    errors: ErrorDetail
