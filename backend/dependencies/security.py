"""Security layer providers: authentication, authorization, user
management, and audit logging.

Mirrors ``backend.dependencies.plugins``/``backend.dependencies.operations``'
own established convention: ``Settings`` is never declared as a parameter
of an ``@lru_cache``'d function (it's a ``pydantic-settings`` model and
isn't hashable) — every cached provider below calls ``get_settings()``
directly in its own body instead.

``resolve_authentication_service()``/``resolve_audit_service()`` exist so
``backend.main.create_app()`` can build the exact same singletons a real
request's own ``Depends(get_authentication_service)`` would resolve to,
without running inside FastAPI's own request-scoped dependency
resolution — the same manual, keyword-argument-exact pattern
``backend.dependencies.operations`` already established for
``resolve_startup_manager()``.
"""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.dependencies.realtime import get_realtime_service, resolve_realtime_service
from backend.realtime.publishers.observability_publisher import (
    RealtimePublishingAuthenticationService,
)
from backend.realtime.services.realtime_service import RealtimeService
from backend.security.audit.audit_service import AuditService
from backend.security.audit.audit_store import AuditStore
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.authentication.jwt_service import JWTService
from backend.security.authentication.password_hasher import PasswordHasher
from backend.security.authentication.session_manager import SessionManager
from backend.security.authorization.authorization_service import AuthorizationService
from backend.security.authorization.policy import Policy, default_policy
from backend.security.users.user_service import UserService
from backend.security.users.user_store import UserStore
from config.settings import get_settings


@lru_cache
def get_password_hasher() -> PasswordHasher:
    """Return the process-wide PasswordHasher singleton. Stateless — cached only for identity reuse."""
    return PasswordHasher()


@lru_cache
def get_user_store() -> UserStore:
    """Return the process-wide UserStore singleton — every user account lives here."""
    return UserStore()


@lru_cache
def get_user_service(
    store: UserStore = Depends(get_user_store),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> UserService:
    """Return the process-wide UserService singleton, seeded with the first-run admin account."""
    settings = get_settings()
    service = UserService(store, password_hasher)
    service.ensure_default_admin(settings.security_admin_username, settings.security_admin_password)
    return service


@lru_cache
def get_policy() -> Policy:
    """Return the process-wide Policy singleton — the built-in role/permission mapping."""
    return default_policy()


@lru_cache
def get_authorization_service(policy: Policy = Depends(get_policy)) -> AuthorizationService:
    """Return the process-wide AuthorizationService singleton."""
    return AuthorizationService(policy)


@lru_cache
def get_jwt_service() -> JWTService:
    """Return the process-wide JWTService singleton, configured from Settings."""
    settings = get_settings()
    return JWTService(
        secret_key=settings.jwt_secret_key, algorithm=settings.jwt_algorithm,
        access_expire_minutes=settings.jwt_access_token_expire_minutes,
        refresh_expire_minutes=settings.jwt_refresh_token_expire_minutes,
        clock_skew_seconds=settings.jwt_clock_skew_seconds,
    )


@lru_cache
def get_session_manager() -> SessionManager:
    """Return the process-wide SessionManager singleton — every active refresh-token session lives here."""
    return SessionManager()


@lru_cache
def get_authentication_service(
    user_service: UserService = Depends(get_user_service),
    jwt_service: JWTService = Depends(get_jwt_service),
    session_manager: SessionManager = Depends(get_session_manager),
    authorization_service: AuthorizationService = Depends(get_authorization_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> AuthenticationService:
    """Return the process-wide AuthenticationService singleton — the only object that should be used for login/logout/refresh/token verification.

    Wrapped in ``RealtimePublishingAuthenticationService`` (Phase 37)
    before being returned — publishes UserLoggedIn/UserLoggedOut around
    ``login()``/``logout()`` with no change to ``AuthenticationService``
    itself. ``authenticate()`` (called on every request by
    ``AuthenticationMiddleware``) is forwarded unchanged.
    """
    service: Any = RealtimePublishingAuthenticationService(
        AuthenticationService(user_service, jwt_service, session_manager, authorization_service), realtime_service
    )
    return service


@lru_cache
def get_audit_store() -> AuditStore:
    """Return the process-wide AuditStore singleton — every audit event lives here."""
    return AuditStore()


@lru_cache
def get_audit_service(store: AuditStore = Depends(get_audit_store)) -> AuditService:
    """Return the process-wide AuditService singleton."""
    return AuditService(store)


def resolve_authentication_service() -> AuthenticationService:
    """Build the process-wide AuthenticationService outside a FastAPI request.

    Called exactly once, from ``backend.main.create_app()`` (to construct
    ``AuthenticationMiddleware``). See this module's own docstring for why
    every call below is keyword-based.
    """
    user_service = get_user_service(store=get_user_store(), password_hasher=get_password_hasher())
    authorization_service = get_authorization_service(policy=get_policy())
    return get_authentication_service(
        user_service=user_service, jwt_service=get_jwt_service(),
        session_manager=get_session_manager(), authorization_service=authorization_service,
        realtime_service=resolve_realtime_service(),
    )


def resolve_audit_service() -> AuditService:
    """Build the process-wide AuditService outside a FastAPI request. See ``resolve_authentication_service()``."""
    return get_audit_service(store=get_audit_store())
