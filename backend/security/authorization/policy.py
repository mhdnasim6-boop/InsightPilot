"""Policy: the single source of authorization truth — which permissions
each role is granted.

A pure, in-memory mapping (mirrors ``backend.approval.policies.ApprovalPolicy``'s
own "policy is a pure decision, not a live registry" shape from Phase 23)
rather than a database table — appropriate for a closed, six-role
vocabulary; a per-tenant/dynamic policy store is named as a future
extension, not attempted here.
"""

from backend.security.authorization.permission import Permission
from backend.security.authorization.role import Role

_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    # Full access to every capability this phase names.
    Role.ADMIN: frozenset(Permission),
    # Runs the actual BI workflow: data in, analysis/plans out. No user
    # management, no system/plugin administration, no audit visibility.
    Role.ANALYST: frozenset({
        Permission.VIEW_DATA, Permission.MANAGE_DATA, Permission.RUN_ANALYSIS, Permission.MANAGE_PLANS,
    }),
    # Read-only over data/analysis outputs. The default "just looking" role.
    Role.VIEWER: frozenset({Permission.VIEW_DATA}),
    # Keeps the platform running: system/operations visibility and plugin
    # lifecycle, plus the audit trail — but doesn't touch business data or
    # user accounts.
    Role.OPERATOR: frozenset({
        Permission.VIEW_DATA, Permission.MANAGE_SYSTEM, Permission.MANAGE_PLUGINS, Permission.VIEW_AUDIT,
    }),
    # Builds and iterates on plugins/extensions against real data, with
    # system visibility for debugging — no user management, no audit.
    Role.DEVELOPER: frozenset({
        Permission.VIEW_DATA, Permission.RUN_ANALYSIS, Permission.MANAGE_PLUGINS, Permission.MANAGE_SYSTEM,
    }),
    # A machine identity for plugin-originated calls (Phase 33's own
    # Plugin & Extension SDK) — deliberately the narrowest role: plugins
    # read data through the same Tool contracts a human Viewer would.
    Role.PLUGIN: frozenset({Permission.VIEW_DATA}),
}


class Policy:
    """Maps a Role to its granted Permissions. The only place that mapping is defined."""

    def __init__(self, role_permissions: dict[Role, frozenset[Permission]] | None = None) -> None:
        self._role_permissions = role_permissions if role_permissions is not None else dict(_ROLE_PERMISSIONS)

    def permissions_for(self, role: Role) -> frozenset[Permission]:
        """Every permission ``role`` is granted. Unknown roles (shouldn't happen — Role is closed) get none."""
        return self._role_permissions.get(role, frozenset())

    def grants(self, role: Role, permission: Permission) -> bool:
        """Whether ``role`` is granted ``permission``."""
        return permission in self.permissions_for(role)

    def all_roles(self) -> list[Role]:
        """Every role this policy knows about, in ``Role`` declaration order."""
        return [role for role in Role if role in self._role_permissions]


def default_policy() -> Policy:
    """The built-in Policy every InsightPilot deployment starts with."""
    return Policy()
