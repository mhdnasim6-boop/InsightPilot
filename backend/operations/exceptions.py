"""Operations layer exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module
(``backend.plugins.exceptions``/``backend.adaptive.exceptions``).
"""

from backend.core.exceptions import InsightPilotError


class OperationsError(InsightPilotError):
    """Base class for every operations-layer exception."""

    status_code = 500
    error_type = "OperationsError"


class UnknownConfigurationProfileError(OperationsError):
    """Raised when ``Settings.active_profile`` names a profile that doesn't exist."""

    status_code = 404
    error_type = "UnknownConfigurationProfileError"


class ConfigurationValidationFailedError(OperationsError):
    """Raised when environment validation finds at least one error-severity issue.

    Only raised where a caller has decided a failed validation should be
    fatal (``StartupManager``'s own "configuration" stage) — the
    validator itself never raises, it always returns a reportable
    ``ConfigurationValidationResult`` instead, per "report problems
    clearly."
    """

    status_code = 422
    error_type = "ConfigurationValidationFailedError"


class UnknownFeatureFlagError(OperationsError):
    """Raised when a feature flag is looked up by an unrecognized name."""

    status_code = 404
    error_type = "UnknownFeatureFlagError"
