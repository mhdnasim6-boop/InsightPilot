"""Security exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module
(``backend.plugins.exceptions``/``backend.operations.exceptions``).
"""

from backend.core.exceptions import InsightPilotError


class SecurityError(InsightPilotError):
    """Base class for every security-layer exception."""

    status_code = 500
    error_type = "SecurityError"


class InvalidCredentialsError(SecurityError):
    """Raised when a login's username/password don't match. Deliberately the
    same error for "no such user" and "wrong password" — never lets a
    caller distinguish the two, to avoid username enumeration."""

    status_code = 401
    error_type = "InvalidCredentialsError"


class AccountDisabledError(SecurityError):
    """Raised when a login (or token use) targets a deactivated user account."""

    status_code = 403
    error_type = "AccountDisabledError"


class AuthenticationRequiredError(SecurityError):
    """Raised by ``get_current_user`` when no valid access token was presented."""

    status_code = 401
    error_type = "AuthenticationRequiredError"


class InvalidTokenError(SecurityError):
    """Raised when a JWT fails signature/structure verification."""

    status_code = 401
    error_type = "InvalidTokenError"


class TokenExpiredError(InvalidTokenError):
    """Raised when a JWT's ``exp`` claim (beyond configured clock-skew leeway) has passed."""

    error_type = "TokenExpiredError"


class TokenRevokedError(InvalidTokenError):
    """Raised when a refresh token's session has been logged out / rotated away."""

    error_type = "TokenRevokedError"


class PermissionDeniedError(SecurityError):
    """Raised by ``AuthorizationService.authorize()`` when a user's role doesn't grant a permission."""

    status_code = 403
    error_type = "PermissionDeniedError"


class UserNotFoundError(SecurityError):
    """Raised when a user is looked up by an unknown id or username."""

    status_code = 404
    error_type = "UserNotFoundError"


class DuplicateUserError(SecurityError):
    """Raised when creating a user whose username or email is already registered."""

    status_code = 409
    error_type = "DuplicateUserError"
