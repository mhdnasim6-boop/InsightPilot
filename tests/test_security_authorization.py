"""Tests for Policy and AuthorizationService."""

import pytest

from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.permission import Permission
from backend.security.authorization.policy import Policy, default_policy
from backend.security.authorization.role import Role
from backend.security.exceptions import PermissionDeniedError
from backend.security.models.authenticated_user import AuthenticatedUser


def test_default_policy_grants_admin_every_permission() -> None:
    policy = default_policy()
    assert policy.permissions_for(Role.ADMIN) == frozenset(Permission)


def test_default_policy_grants_viewer_only_view_data() -> None:
    policy = default_policy()
    assert policy.permissions_for(Role.VIEWER) == frozenset({Permission.VIEW_DATA})


def test_default_policy_grants_no_role_manage_users_except_admin() -> None:
    policy = default_policy()
    for role in Role:
        if role is Role.ADMIN:
            assert policy.grants(role, Permission.MANAGE_USERS)
        else:
            assert not policy.grants(role, Permission.MANAGE_USERS)


def test_all_roles_returns_every_role() -> None:
    assert set(default_policy().all_roles()) == set(Role)


def test_custom_policy_overrides_the_default_mapping() -> None:
    policy = Policy({Role.VIEWER: frozenset({Permission.MANAGE_USERS})})
    assert policy.grants(Role.VIEWER, Permission.MANAGE_USERS)
    assert not policy.grants(Role.VIEWER, Permission.VIEW_DATA)


def _user(role: Role) -> AuthenticatedUser:
    return AuthenticatedUser(user_id="u1", username="u", role=role, permissions=default_policy().permissions_for(role))


def test_authorization_service_has_permission() -> None:
    service = AuthorizationService(default_policy())
    assert service.has_permission(_user(Role.ANALYST), Permission.RUN_ANALYSIS)
    assert not service.has_permission(_user(Role.ANALYST), Permission.MANAGE_USERS)


def test_authorization_service_authorize_raises_for_missing_permission() -> None:
    service = AuthorizationService(default_policy())
    with pytest.raises(PermissionDeniedError):
        service.authorize(_user(Role.VIEWER), Permission.MANAGE_USERS)


def test_authorization_service_authorize_does_not_raise_when_granted() -> None:
    service = AuthorizationService(default_policy())
    service.authorize(_user(Role.ADMIN), Permission.MANAGE_USERS)  # must not raise


def test_authorization_service_roles_catalog_matches_policy() -> None:
    service = AuthorizationService(default_policy())
    catalog = service.roles_catalog()
    assert catalog[Role.PLUGIN] == frozenset({Permission.VIEW_DATA})
