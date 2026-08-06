"""ConfigurationProfile: a named set of Settings overrides, plus the five
built-in profiles this phase specifies (development/testing/staging/
production/local).

Profiles "inherit defaults" literally: a profile's ``overrides`` dict only
ever names the handful of fields it actually wants to change (e.g.
``debug``/``log_level``/``host``) — every field it doesn't mention keeps
whatever ``Settings`` itself already resolved (its own declared default,
or a real environment variable). ``ConfigurationLoader`` is what applies
this; this module only declares the data.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ConfigurationProfileName(str, Enum):
    """Every operational profile InsightPilot recognizes.

    Deliberately a *separate* vocabulary from ``Settings.environment``
    (``development``/``staging``/``production`` only, unchanged since
    Phase 1 and still what ``create_app()``'s own production+debug guard
    checks) — a "profile" is a broader operational concept this phase
    adds (it also covers ``testing``/``local``), not a replacement for
    that existing field.
    """

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"


class ConfigurationProfile(BaseModel):
    """One profile's overrides over ``Settings``' own defaults."""

    model_config = ConfigDict(frozen=True)

    name: ConfigurationProfileName
    description: str = ""
    overrides: dict[str, bool | str | int | float] = Field(default_factory=dict)


_PROFILES: dict[ConfigurationProfileName, ConfigurationProfile] = {
    ConfigurationProfileName.DEVELOPMENT: ConfigurationProfile(
        name=ConfigurationProfileName.DEVELOPMENT,
        description="Local development against Settings' own defaults — a deliberate no-op profile.",
        overrides={},
    ),
    ConfigurationProfileName.LOCAL: ConfigurationProfile(
        name=ConfigurationProfileName.LOCAL,
        description="Single-machine local run: verbose logging, loopback-only host.",
        overrides={"debug": True, "log_level": "DEBUG", "host": "127.0.0.1"},
    ),
    ConfigurationProfileName.TESTING: ConfigurationProfile(
        name=ConfigurationProfileName.TESTING,
        description="Automated test runs: quiet logging, debug assertions on.",
        overrides={"debug": True, "log_level": "WARNING"},
    ),
    ConfigurationProfileName.STAGING: ConfigurationProfile(
        name=ConfigurationProfileName.STAGING,
        description="Pre-production verification environment.",
        overrides={"debug": False, "log_level": "INFO"},
    ),
    ConfigurationProfileName.PRODUCTION: ConfigurationProfile(
        name=ConfigurationProfileName.PRODUCTION,
        description="Production: debug disabled, quiet logging.",
        overrides={"debug": False, "log_level": "WARNING"},
    ),
}


def get_profile(name: ConfigurationProfileName) -> ConfigurationProfile:
    """Return the built-in profile for ``name``. Every ``ConfigurationProfileName`` member has one."""
    return _PROFILES[name]


def list_profiles() -> list[ConfigurationProfile]:
    """Every built-in profile, in ``ConfigurationProfileName`` declaration order."""
    return [_PROFILES[name] for name in ConfigurationProfileName]
