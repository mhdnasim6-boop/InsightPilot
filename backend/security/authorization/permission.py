"""Permission: the closed vocabulary of things a role can be granted."""

from enum import Enum


class Permission(str, Enum):
    """Every permission InsightPilot's security layer recognizes.

    Scoped to the app's real capability surface (data/analysis, plans,
    plugins, operations, user management, audit) rather than one
    permission per REST endpoint — a single ``RUN_ANALYSIS`` grant covers
    every analysis/visualization/execution endpoint the same way, since
    they're all facets of one capability, not independent ones.
    """

    VIEW_DATA = "view_data"
    MANAGE_DATA = "manage_data"
    RUN_ANALYSIS = "run_analysis"
    MANAGE_PLANS = "manage_plans"
    MANAGE_PLUGINS = "manage_plugins"
    MANAGE_SYSTEM = "manage_system"
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT = "view_audit"
