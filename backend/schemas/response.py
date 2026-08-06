"""Unified success response shape returned by every endpoint.

Pairs with :class:`backend.schemas.errors.ErrorResponse` for failures —
together they form the project-wide API envelope: every response is
either ``{success: true, message, data}`` or ``{success: false, message,
errors}``.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    """Unified success envelope."""

    success: bool = Field(default=True)
    message: str
    data: DataT

    @classmethod
    def ok(cls, data: DataT, message: str = "Success") -> "SuccessResponse[DataT]":
        """Build a success envelope around the given payload."""
        return cls(success=True, message=message, data=data)
