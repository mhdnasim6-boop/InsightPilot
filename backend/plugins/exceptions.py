"""Plugin exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module
(``backend.adaptive.exceptions``/``backend.reflection.exceptions``).
"""

from backend.core.exceptions import InsightPilotError


class PluginError(InsightPilotError):
    """Base class for every plugin-layer exception."""

    status_code = 500
    error_type = "PluginError"


class PluginNotFoundError(PluginError):
    """Raised when a plugin is looked up by an unregistered plugin_id."""

    status_code = 404
    error_type = "PluginNotFoundError"


class PluginValidationError(PluginError):
    """Raised when a discovered plugin's manifest fails validation.

    Never propagates out of ``PluginRegistry.load_all()`` — caught there
    per plugin and recorded as a FAILED lifecycle state instead, per
    "one bad plugin should not affect the platform."
    """

    status_code = 422
    error_type = "PluginValidationError"


class DuplicatePluginError(PluginValidationError):
    """Raised when two discovered plugins declare the same manifest id."""

    error_type = "DuplicatePluginError"


class PluginDependencyError(PluginValidationError):
    """Raised for a missing dependency or a dependency cycle among plugin ids."""

    error_type = "PluginDependencyError"


class PluginVersionError(PluginValidationError):
    """Raised when a plugin declares an incompatible InsightPilot version."""

    error_type = "PluginVersionError"


class PluginLoadError(PluginError):
    """Raised when importing or instantiating a discovered plugin module fails."""

    status_code = 500
    error_type = "PluginLoadError"
