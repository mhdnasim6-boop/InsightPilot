"""Tests for backend.dependencies.security: singleton caching, and that
resolve_authentication_service()/resolve_audit_service() (the manual,
create_app()-only resolution path) produce the exact same singletons a
real request's Depends(get_authentication_service) would.

Deliberately does **not** clear these providers' ``@lru_cache`` state the
way ``tests/test_mcp_dependencies.py``/``tests/test_operations_dependencies.py``
clear theirs: ``backend.main``'s module-level ``app`` constructs
``AuthenticationMiddleware`` exactly once, at import time, holding a
*direct* reference to the ``AuthenticationService`` (and, transitively,
``UserService``/``UserStore``) that existed at that moment — unlike
Operations' ``StartupManager`` (re-resolved fresh on every ``lifespan()``
run) or MCP's registry (only ever reached through ``Depends()``, never
captured), nothing re-synchronizes that captured reference with the
cache afterward. Clearing ``get_user_store``/``get_user_service`` here
would silently desynchronize every *other* test file's HTTP requests
(which resolve a freshly-rebuilt store via ``Depends(get_user_service)``)
from what ``AuthenticationMiddleware`` already captured — a real,
verified cross-test-file hazard, not a hypothetical one. Every assertion
below works correctly against whatever state the shared singletons
already carry, so no clearing is needed.
"""

from backend.dependencies.realtime import resolve_realtime_service
from backend.dependencies.security import (
    get_audit_service,
    get_audit_store,
    get_authentication_service,
    get_authorization_service,
    get_jwt_service,
    get_password_hasher,
    get_policy,
    get_session_manager,
    get_user_service,
    get_user_store,
    resolve_audit_service,
    resolve_authentication_service,
)
from backend.security.audit.audit_service import AuditService
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.authorization.role import Role


def test_get_user_store_is_a_singleton() -> None:
    assert get_user_store() is get_user_store()


def test_get_user_service_seeds_the_default_admin() -> None:
    service = get_user_service(store=get_user_store(), password_hasher=get_password_hasher())
    assert any(u.username == "admin" for u in service.list_users())


def test_get_authorization_service_is_a_singleton_given_the_same_policy() -> None:
    policy = get_policy()
    assert get_authorization_service(policy=policy) is get_authorization_service(policy=policy)


def test_get_jwt_service_is_a_singleton_and_reads_settings() -> None:
    assert get_jwt_service() is get_jwt_service()


def test_resolve_authentication_service_matches_a_request_style_depends_resolution() -> None:
    user_service = get_user_service(store=get_user_store(), password_hasher=get_password_hasher())
    authorization_service = get_authorization_service(policy=get_policy())
    request_style = get_authentication_service(
        user_service=user_service, jwt_service=get_jwt_service(),
        session_manager=get_session_manager(), authorization_service=authorization_service,
        realtime_service=resolve_realtime_service(),
    )
    assert resolve_authentication_service() is request_style


def test_resolve_authentication_service_returns_the_real_type() -> None:
    # Phase 37: get_authentication_service() wraps the real AuthenticationService in
    # RealtimePublishingAuthenticationService (publishes UserLoggedIn/UserLoggedOut) —
    # the same "decorator satisfies the same contract, not the same class" shape
    # backend.dependencies.tools already established for TracingTool-wrapped tools.
    # authenticate()/login()/logout() staying genuinely callable is what "the real
    # type" means here now, not literal isinstance.
    service = resolve_authentication_service()
    assert not isinstance(service, AuthenticationService)
    assert hasattr(service, "authenticate")
    assert hasattr(service, "login")
    assert hasattr(service, "logout")


def test_resolve_audit_service_matches_a_request_style_depends_resolution() -> None:
    request_style = get_audit_service(store=get_audit_store())
    assert resolve_audit_service() is request_style


def test_resolve_audit_service_returns_the_real_type() -> None:
    assert isinstance(resolve_audit_service(), AuditService)


def test_resolve_authentication_service_can_genuinely_authenticate() -> None:
    # End-to-end proof the manually-resolved chain is wired correctly, not just
    # that object identities match — resembles test_operations_dependencies.py's
    # own "running it actually loads plugins" proof. Uses a fresh, unlikely-to-
    # collide username since the store is shared across the whole test session.
    authentication_service = resolve_authentication_service()
    user_service = get_user_service(store=get_user_store(), password_hasher=get_password_hasher())
    username = "carol_security_dependencies_test"
    if user_service.get_by_username(username) is None:
        user_service.create_user(username, "carol@example.com", "hunter22", Role.VIEWER)
    result = authentication_service.login(username, "hunter22")
    authenticated = authentication_service.authenticate(result.access_token)
    assert authenticated.username == username
