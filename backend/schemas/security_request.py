"""Request models for /api/v1/security's user-management and token endpoints.

Mirrors every other phase's own ``backend/schemas/*_request.py`` module —
these are REST-only shapes, distinct from the security domain's own
``backend/security/models/`` (used for the explicitly-named
LoginRequest/LoginResponse/Token/AuthenticatedUser).
"""

from pydantic import BaseModel, EmailStr, Field

from backend.security.authorization.role import Role


class RefreshTokenRequest(BaseModel):
    """Body for POST /refresh-token and POST /logout — both act on a refresh token."""

    refresh_token: str = Field(..., min_length=1)


class CreateUserRequest(BaseModel):
    """Body for POST /users."""

    username: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Role
    full_name: str = ""


class UpdateUserRequest(BaseModel):
    """Body for PUT /users/{id} — every field optional, only given ones change."""

    email: EmailStr | None = None
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)
