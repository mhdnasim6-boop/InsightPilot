"""ConfigurationLoader: resolves the active ConfigurationProfile's
overrides onto an already environment-resolved Settings instance.

Environment variables always win. ``pydantic-settings`` gives constructor
keyword arguments *higher* priority than environment variables (confirmed
empirically, not assumed — ``Settings(app_name="x")`` beats
``APP_NAME=y`` in the environment every time), so a profile's overrides
can never simply be passed as ``Settings(**overrides)`` without silently
clobbering a real, explicitly-set environment variable. Instead, this
loader starts from ``Settings`` as already resolved by ``get_settings()``
(env vars / ``.env`` / field defaults — completely unchanged, no new
parsing) and applies a profile override for a field only when that
field's *current* value still equals its class-declared default — i.e.
nothing already set it via the environment. The one edge case this can't
distinguish (an environment variable whose value happens to equal the
field's own default) is a documented limitation, not a correctness bug in
practice: the resulting value is identical either way.
"""

from backend.operations.configuration.configuration_profile import (
    ConfigurationProfileName,
    get_profile,
)
from backend.operations.exceptions import UnknownConfigurationProfileError
from config.settings import Settings, get_settings


class ConfigurationLoader:
    """Applies ``Settings.active_profile``'s overrides on top of environment-resolved Settings."""

    def load(self, settings: Settings | None = None) -> Settings:
        """Return a Settings instance with the active profile's overrides applied.

        ``settings`` defaults to ``get_settings()`` (the same singleton
        every other provider in this codebase uses) so callers never need
        to re-parse the environment themselves.
        """
        base = settings if settings is not None else get_settings()
        profile = get_profile(self._resolve_profile_name(base))
        if not profile.overrides:
            return base

        field_defaults = {name: field.default for name, field in type(base).model_fields.items()}
        resolved_overrides = {
            key: value
            for key, value in profile.overrides.items()
            if key in field_defaults and getattr(base, key) == field_defaults[key]
        }
        if not resolved_overrides:
            return base
        return base.model_copy(update=resolved_overrides)

    def _resolve_profile_name(self, settings: Settings) -> ConfigurationProfileName:
        try:
            return ConfigurationProfileName(settings.active_profile)
        except ValueError as exc:
            raise UnknownConfigurationProfileError(
                f"Unknown configuration profile: '{settings.active_profile}'."
            ) from exc
