"""AuthenticationService: the only public entry point for login/logout/
refresh/token-verification — orchestrates JWTService, SessionManager,
UserService, and AuthorizationService without any of them needing to
know about each other.
"""

from backend.security.authentication.jwt_service import JWTService
from backend.security.authentication.session_manager import SessionManager
from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.role import Role
from backend.security.exceptions import (
    AccountDisabledError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from backend.security.models.authenticated_user import AuthenticatedUser
from backend.security.models.login_response import LoginResponse
from backend.security.models.token import TokenType
from backend.security.users.profile import UserProfile
from backend.security.users.user_service import UserService
from backend.utils.time import utc_now


class AuthenticationService:
    """Login, logout, refresh, and access-token verification."""

    def __init__(
        self, user_service: UserService, jwt_service: JWTService,
        session_manager: SessionManager, authorization_service: AuthorizationService,
    ) -> None:
        self._user_service = user_service
        self._jwt_service = jwt_service
        self._session_manager = session_manager
        self._authorization_service = authorization_service

    def authenticate(self, access_token: str) -> AuthenticatedUser:
        """Verify an access token and return the caller's current identity.

        Permissions are recomputed from the live Policy on every call, not
        read from the token — a Policy change takes effect on this user's
        very next request, not just their next login. Raises
        TokenExpiredError/InvalidTokenError (both subclasses of
        SecurityError) for anything wrong with the token itself.
        """
        claims = self._jwt_service.decode(access_token, TokenType.ACCESS)
        role = Role(claims.role)
        permissions = self._authorization_service.permissions_for(role)
        return AuthenticatedUser(user_id=claims.sub, username=claims.username, role=role, permissions=permissions)

    def login(self, username: str, password: str) -> LoginResponse:
        """Verify credentials and issue a fresh access/refresh token pair.
        Raises InvalidCredentialsError for any bad-username/bad-password/inactive-account
        case (deliberately indistinguishable, to avoid username enumeration)."""
        user = self._user_service.verify_credentials(username, password)
        if user is None:
            raise InvalidCredentialsError("Incorrect username or password.")
        return self._issue_tokens(user.user_id)

    def logout(self, refresh_token: str) -> None:
        """Revoke the session behind a refresh token. Idempotent — logging out twice
        with the same (already-revoked) token is not an error."""
        claims = self._jwt_service.decode(refresh_token, TokenType.REFRESH)
        if claims.jti is not None:
            self._session_manager.revoke(claims.jti)

    def refresh(self, refresh_token: str) -> LoginResponse:
        """Verify a refresh token's session is still active, then rotate it: the old
        session is revoked and a brand-new access/refresh pair (new session) is
        issued — refresh-token rotation, so a stolen-and-reused old refresh token
        is rejected the moment the legitimate client refreshes first."""
        claims = self._jwt_service.decode(refresh_token, TokenType.REFRESH)
        if claims.jti is None:
            raise InvalidTokenError("Refresh token is missing its session id.")
        self._session_manager.require_active(claims.jti)
        self._session_manager.revoke(claims.jti)

        user = self._user_service.get(claims.sub)
        if not user.is_active:
            raise AccountDisabledError(f"User '{user.username}' is deactivated.")
        return self._issue_tokens(user.user_id)

    def _issue_tokens(self, user_id: str) -> LoginResponse:
        user = self._user_service.get(user_id)
        access = self._jwt_service.create_access_token(user)
        refresh = self._jwt_service.create_refresh_token(user)

        claims = self._jwt_service.decode(refresh.value, TokenType.REFRESH)
        if claims.jti is not None:
            self._session_manager.create(claims.jti, user.user_id, refresh.expires_at)

        expires_in = int((access.expires_at - utc_now()).total_seconds())
        return LoginResponse(
            access_token=access.value, refresh_token=refresh.value, token_type="bearer",
            expires_in=max(expires_in, 0), user=UserProfile.from_user(user),
        )
