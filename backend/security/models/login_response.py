"""LoginResponse: what POST /login and POST /refresh-token both return —
a fresh access/refresh token pair plus the caller's own profile, so a
client never needs a separate GET /me call just to render "who am I."
"""

from pydantic import BaseModel

from backend.security.users.profile import UserProfile


class LoginResponse(BaseModel):
    """A fresh token pair plus the authenticated user's profile."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile
