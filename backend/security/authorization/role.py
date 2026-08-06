"""Role: the closed vocabulary of built-in roles this phase names."""

from enum import Enum


class Role(str, Enum):
    """Every built-in role InsightPilot's security layer recognizes.

    Custom/dynamic roles are a named future extension (see README's
    "RBAC editor" entry) — this phase's own scope is exactly these six.
    """

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    PLUGIN = "plugin"
