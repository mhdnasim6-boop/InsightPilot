"""User: the full, internal account record — includes the password hash.

Never serialized directly over REST (see ``profile.py`` for the public-safe
view) and never embedded in a JWT (tokens carry only ``user_id``/
``username``/``role`` — see ``security.models.token``).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.security.authorization.role import Role


class User(BaseModel):
    """One account. ``hashed_password`` is a PasswordHasher-produced string, never plaintext."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    email: str
    full_name: str
    hashed_password: str
    role: Role
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
