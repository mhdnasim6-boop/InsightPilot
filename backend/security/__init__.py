"""Security layer: authentication, authorization, user management, and
audit logging — production-grade, entirely additive.

No existing service gains security logic and none imports
``AuthenticationService``: security is enforced only through
``backend.security.middleware`` (attaches identity, records audit) and
FastAPI dependencies (``get_current_user``/``require_permission``) that
individual routers opt into — exactly like every other cross-cutting
concern in this codebase (observability tracing, DI-provided services).
"""
