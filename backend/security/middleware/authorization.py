"""Authorization gate: ``get_current_user``/``require_permission()`` — FastAPI
dependencies, not a Starlette ``BaseHTTPMiddleware`` class.

This is a deliberate choice, not a shortcut: unlike authentication
(identify the caller — the same check for every request) or request
context (tag every request with a correlation id), *authorization* needs
a different answer per endpoint (``GET /users`` needs ``MANAGE_USERS``,
``GET /audit`` needs ``VIEW_AUDIT``, ...). A blanket ASGI middleware has
no routing table to know which permission a given path needs without
inventing one; FastAPI's own documented pattern for exactly this is a
``Depends()``-based guard declared per-route — the same mechanism every
other cross-cutting per-route concern in this codebase already uses
(``Depends(get_health_service)``, etc.). "Each endpoint declares required
permission through DI" is satisfied literally: ``Depends(require_permission(...))``.

``require_permission()`` builds its own local, stateless ``AuthorizationService``
rather than depending on ``backend.dependencies.security.get_authorization_service``
— not a divergent second implementation, a deliberate layering choice:
no ``backend/<domain>/`` package anywhere in this codebase imports from
``backend/dependencies/`` (only ``backend/api/v1/*`` and ``backend/main.py``
do), and ``AuthorizationService``/``Policy`` are pure, hardcoded, and
have no mutable state to keep in sync across instances — constructing
one fresh is behaviorally identical to reusing the cached singleton.
"""

from collections.abc import Callable

from fastapi import Depends, Request

from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.permission import Permission
from backend.security.authorization.policy import default_policy
from backend.security.exceptions import AuthenticationRequiredError
from backend.security.models.authenticated_user import AuthenticatedUser


def get_current_user(request: Request) -> AuthenticatedUser:
    """The caller's identity, as resolved by AuthenticationMiddleware. Raises
    AuthenticationRequiredError (401) if no valid access token was presented."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise AuthenticationRequiredError("A valid access token is required.")
    return user


def require_permission(permission: Permission) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Build a dependency that requires ``permission``. Usage:
    ``Depends(require_permission(Permission.MANAGE_USERS))``. No endpoint using this
    ever inspects ``user.role``/``user.permissions`` itself — this is the only gate.
    """
    authorization_service = AuthorizationService(default_policy())

    def _dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        authorization_service.authorize(user, permission)
        return user

    return _dependency
