"""Security endpoints: login/logout/refresh, current-user, user
management, audit log, and the roles/permissions catalog — thin wrappers
over backend.security, exactly like every other router in this codebase.

Authorization is declared per-endpoint via
``Depends(require_permission(...))`` — no handler below inspects
``user.role``/``user.permissions`` itself.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.security import (
    get_audit_service,
    get_authentication_service,
    get_authorization_service,
    get_user_service,
)
from backend.schemas.response import SuccessResponse
from backend.schemas.security_request import (
    CreateUserRequest,
    RefreshTokenRequest,
    UpdateUserRequest,
)
from backend.security.audit.audit_event import AuditEvent
from backend.security.audit.audit_service import AuditService
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.permission import Permission
from backend.security.middleware.authorization import (
    get_current_user,
    require_permission,
)
from backend.security.models.authenticated_user import AuthenticatedUser
from backend.security.models.login_request import LoginRequest
from backend.security.models.login_response import LoginResponse
from backend.security.users.profile import UserProfile
from backend.security.users.user_service import UserService

router = APIRouter()


@router.post("/login", response_model=SuccessResponse[LoginResponse], summary="Log in")
async def login(
    body: LoginRequest, authentication_service: AuthenticationService = Depends(get_authentication_service),
) -> SuccessResponse[LoginResponse]:
    """Verify credentials and issue a fresh access/refresh token pair. Raises
    InvalidCredentialsError (401) for any bad-username/bad-password/inactive-account case."""
    result = authentication_service.login(body.username, body.password)
    return SuccessResponse.ok(data=result, message=f"Welcome, {result.user.username}.")


@router.post("/logout", response_model=SuccessResponse[bool], summary="Log out")
async def logout(
    body: RefreshTokenRequest, authentication_service: AuthenticationService = Depends(get_authentication_service),
) -> SuccessResponse[bool]:
    """Revoke the session behind a refresh token. Acts on the refresh token alone —
    deliberately doesn't require a still-valid access token, since logging out after
    the access token has already expired is a normal, common case."""
    authentication_service.logout(body.refresh_token)
    return SuccessResponse.ok(data=True, message="Logged out.")


@router.post("/refresh-token", response_model=SuccessResponse[LoginResponse], summary="Refresh a token pair")
async def refresh_token(
    body: RefreshTokenRequest, authentication_service: AuthenticationService = Depends(get_authentication_service),
) -> SuccessResponse[LoginResponse]:
    """Exchange a still-active refresh token for a brand-new access/refresh pair
    (rotation: the old refresh token's session is revoked in the same call)."""
    result = authentication_service.refresh(body.refresh_token)
    return SuccessResponse.ok(data=result, message="Token refreshed.")


@router.get("/me", response_model=SuccessResponse[UserProfile], summary="Current user")
async def get_me(
    user: AuthenticatedUser = Depends(get_current_user), user_service: UserService = Depends(get_user_service),
) -> SuccessResponse[UserProfile]:
    """The caller's own, freshly-fetched profile (not just the access token's own claims —
    reflects the latest role/is_active from the user store)."""
    profile = UserProfile.from_user(user_service.get(user.user_id))
    return SuccessResponse.ok(data=profile, message="Current user fetched.")


@router.get("/users", response_model=SuccessResponse[list[UserProfile]], summary="List users")
async def list_users(
    user_service: UserService = Depends(get_user_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_USERS)),
) -> SuccessResponse[list[UserProfile]]:
    """Every registered user's public profile."""
    return SuccessResponse.ok(data=user_service.list_users(), message="Users fetched.")


@router.post("/users", response_model=SuccessResponse[UserProfile], summary="Create a user")
async def create_user(
    body: CreateUserRequest,
    user_service: UserService = Depends(get_user_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_USERS)),
) -> SuccessResponse[UserProfile]:
    """Create a new user account. Raises DuplicateUserError (409) if the username is taken."""
    user = user_service.create_user(
        username=body.username, email=body.email, password=body.password, role=body.role, full_name=body.full_name,
    )
    return SuccessResponse.ok(data=UserProfile.from_user(user), message=f"User '{user.username}' created.")


@router.put("/users/{user_id}", response_model=SuccessResponse[UserProfile], summary="Update a user")
async def update_user(
    user_id: str, body: UpdateUserRequest,
    user_service: UserService = Depends(get_user_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_USERS)),
) -> SuccessResponse[UserProfile]:
    """Update one or more fields of an existing user. Raises UserNotFoundError (404) if unknown."""
    user = user_service.update_user(
        user_id, email=body.email, full_name=body.full_name, role=body.role,
        is_active=body.is_active, password=body.password,
    )
    return SuccessResponse.ok(data=UserProfile.from_user(user), message=f"User '{user.username}' updated.")


@router.delete("/users/{user_id}", response_model=SuccessResponse[UserProfile], summary="Delete a user")
async def delete_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_USERS)),
) -> SuccessResponse[UserProfile]:
    """Delete a user account. Raises UserNotFoundError (404) if unknown. Returns the removed profile."""
    user = user_service.get(user_id)
    user_service.delete_user(user_id)
    return SuccessResponse.ok(data=UserProfile.from_user(user), message=f"User '{user.username}' deleted.")


@router.get("/audit", response_model=SuccessResponse[list[AuditEvent]], summary="Audit log")
async def get_audit_log(
    limit: int = 100,
    audit_service: AuditService = Depends(get_audit_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_AUDIT)),
) -> SuccessResponse[list[AuditEvent]]:
    """Most-recent-first audit events."""
    return SuccessResponse.ok(data=audit_service.list_events(limit=limit), message="Audit log fetched.")


@router.get("/roles", response_model=SuccessResponse[dict[str, list[Permission]]], summary="Roles catalog")
async def get_roles(
    authorization_service: AuthorizationService = Depends(get_authorization_service),
    _: AuthenticatedUser = Depends(get_current_user),
) -> SuccessResponse[dict[str, list[Permission]]]:
    """Every built-in role mapped to its granted permissions. Any authenticated user may view this."""
    catalog = {role.value: sorted(permissions, key=lambda p: p.value) for role, permissions in authorization_service.roles_catalog().items()}
    return SuccessResponse.ok(data=catalog, message="Roles fetched.")


@router.get("/permissions", response_model=SuccessResponse[list[Permission]], summary="Permissions catalog")
async def get_permissions(_: AuthenticatedUser = Depends(get_current_user)) -> SuccessResponse[list[Permission]]:
    """Every permission this deployment recognizes. Any authenticated user may view this."""
    return SuccessResponse.ok(data=sorted(Permission, key=lambda p: p.value), message="Permissions fetched.")
