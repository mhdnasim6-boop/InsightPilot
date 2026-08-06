"""UserProfile: the public-safe view of a User — everything except the
password hash. What GET /users, GET /me, and LoginResponse all return.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.security.authorization.role import Role
from backend.security.users.user import User


class UserProfile(BaseModel):
    """A User with its ``hashed_password`` field removed."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserProfile":
        return cls(
            user_id=user.user_id, username=user.username, email=user.email, full_name=user.full_name,
            role=user.role, is_active=user.is_active, created_at=user.created_at, updated_at=user.updated_at,
        )
