"""LoginRequest: the shape POST /login accepts."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Username/password credentials."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
