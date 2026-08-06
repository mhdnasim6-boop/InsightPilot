"""AuthenticatedUser: the request-scoped identity AuthenticationMiddleware
attaches to ``request.state.user`` — never the full ``User`` (no hashed
password, no email) and never a stale permissions snapshot from login
time. ``permissions`` is recomputed from the current Policy on every
request (via ``AuthenticationService.authenticate()``), so a Policy
change takes effect on a caller's very next request, not just their next
login.
"""

from pydantic import BaseModel, ConfigDict

from backend.security.authorization.permission import Permission
from backend.security.authorization.role import Role


class AuthenticatedUser(BaseModel):
    """Who is making this request, and what they're currently allowed to do."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    role: Role
    permissions: frozenset[Permission]
