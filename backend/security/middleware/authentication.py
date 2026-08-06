"""AuthenticationMiddleware: resolves the caller's identity for every
request (``request.state.user``), and automatically records an audit
event for every request that turned out to be authenticated.

Deliberately never *rejects* a request itself — a missing/invalid/expired
token just leaves ``request.state.user`` as ``None``, which is exactly
what ``backend.security.middleware.authorization.get_current_user``
turns into a 401 for the endpoints that actually require it. This is
what lets `/login`/`/docs`/`/api/v1/health` keep working with no token at
all, without this middleware needing a hardcoded list of "public paths."

Audit logging lives here, not in any business service, satisfying "audit
logging must be automatic" and "nothing inside business services should
know it exists" simultaneously: it fires once, in one place, only for
requests this middleware could actually attribute to a real user.
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.security.audit.audit_service import AuditService
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.exceptions import SecurityError

_AUTH_HEADER = "Authorization"
_SCHEME_PREFIX = "Bearer "


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Attaches ``request.state.user`` (an ``AuthenticatedUser`` or ``None``) and
    records an audit event for every request that resolved to a real user."""

    def __init__(
        self, app: object, authentication_service: AuthenticationService, audit_service: AuditService,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._authentication_service = authentication_service
        self._audit_service = audit_service

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request.state.user = None
        token = _extract_bearer_token(request)
        if token is not None:
            try:
                request.state.user = self._authentication_service.authenticate(token)
            except SecurityError:
                request.state.user = None

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        user = request.state.user
        if user is not None:
            self._audit_service.record(
                user_id=user.user_id, username=user.username,
                action=f"{request.method} {request.url.path}",
                endpoint=request.url.path, method=request.method, duration_ms=duration_ms,
                status_code=response.status_code, request_id=getattr(request.state, "request_id", ""),
            )
        return response


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get(_AUTH_HEADER)
    if header is None or not header.startswith(_SCHEME_PREFIX):
        return None
    return header[len(_SCHEME_PREFIX):]
