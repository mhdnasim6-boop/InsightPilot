"""AuthorizationService: the only object that decides "is this permission granted."

Every REST endpoint that needs a permission check reaches this through
``backend.security.middleware.authorization.require_permission()`` — no
endpoint ever inspects ``user.role``/``user.permissions`` itself.
"""

from backend.security.authorization.permission import Permission
from backend.security.authorization.policy import Policy
from backend.security.authorization.role import Role
from backend.security.exceptions import PermissionDeniedError
from backend.security.models.authenticated_user import AuthenticatedUser


class AuthorizationService:
    """Wraps a Policy: computes a role's permissions, and enforces a required one."""

    def __init__(self, policy: Policy) -> None:
        self._policy = policy

    def permissions_for(self, role: Role) -> frozenset[Permission]:
        """Every permission ``role`` currently grants, per the active Policy."""
        return self._policy.permissions_for(role)

    def has_permission(self, user: AuthenticatedUser, permission: Permission) -> bool:
        """Whether ``user`` currently holds ``permission``."""
        return permission in user.permissions

    def authorize(self, user: AuthenticatedUser, permission: Permission) -> None:
        """Raise PermissionDeniedError unless ``user`` holds ``permission``."""
        if not self.has_permission(user, permission):
            raise PermissionDeniedError(
                f"User '{user.username}' (role: {user.role.value}) lacks permission '{permission.value}'."
            )

    def roles_catalog(self) -> dict[Role, frozenset[Permission]]:
        """Every built-in role mapped to its granted permissions — what GET /roles returns."""
        return {role: self._policy.permissions_for(role) for role in self._policy.all_roles()}
