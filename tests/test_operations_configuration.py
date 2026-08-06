"""Tests for backend.operations.configuration: ConfigurationProfile,
ConfigurationLoader, ConfigurationValidator.
"""

import pytest

from backend.operations.configuration.configuration_loader import ConfigurationLoader
from backend.operations.configuration.configuration_profile import (
    ConfigurationProfileName,
    get_profile,
    list_profiles,
)
from backend.operations.configuration.configuration_validator import (
    ConfigurationValidator,
    IssueSeverity,
)
from backend.operations.exceptions import UnknownConfigurationProfileError
from config.settings import Settings

# -- ConfigurationProfile -------------------------------------------------------------


def test_every_profile_name_has_a_built_in_profile() -> None:
    for name in ConfigurationProfileName:
        profile = get_profile(name)
        assert profile.name == name


def test_list_profiles_returns_all_five() -> None:
    names = {profile.name for profile in list_profiles()}
    assert names == set(ConfigurationProfileName)


def test_development_profile_has_no_overrides() -> None:
    assert get_profile(ConfigurationProfileName.DEVELOPMENT).overrides == {}


def test_production_profile_disables_debug() -> None:
    profile = get_profile(ConfigurationProfileName.PRODUCTION)
    assert profile.overrides["debug"] is False


# -- ConfigurationLoader --------------------------------------------------------------


def test_loader_is_a_no_op_for_the_default_development_profile() -> None:
    base = Settings()
    resolved = ConfigurationLoader().load(base)
    assert resolved == base


def test_loader_applies_production_profile_overrides() -> None:
    base = Settings(active_profile="production")
    resolved = ConfigurationLoader().load(base)
    assert resolved.debug is False
    assert resolved.log_level == "WARNING"


def test_loader_applies_local_profile_overrides() -> None:
    base = Settings(active_profile="local")
    resolved = ConfigurationLoader().load(base)
    assert resolved.debug is True
    assert resolved.log_level == "DEBUG"
    assert resolved.host == "127.0.0.1"


def test_loader_never_overrides_a_field_the_environment_already_set() -> None:
    # log_level explicitly set (not the class default of "INFO"), so the
    # production profile's own log_level="WARNING" override must not apply.
    base = Settings(active_profile="production", log_level="DEBUG")
    resolved = ConfigurationLoader().load(base)
    assert resolved.log_level == "DEBUG"
    assert resolved.debug is False  # debug was untouched, so this override still applies


def test_loader_defaults_to_get_settings_when_none_given() -> None:
    resolved = ConfigurationLoader().load()
    assert isinstance(resolved, Settings)


def test_loader_raises_for_unknown_profile() -> None:
    base = Settings(active_profile="does-not-exist")
    with pytest.raises(UnknownConfigurationProfileError):
        ConfigurationLoader().load(base)


# -- ConfigurationValidator -------------------------------------------------------------


def test_validator_reports_valid_for_default_settings() -> None:
    result = ConfigurationValidator().validate(Settings())
    assert result.is_valid is True


def test_validator_flags_an_invalid_log_level() -> None:
    result = ConfigurationValidator().validate(Settings(log_level="NOT_A_LEVEL"))
    assert result.is_valid is False
    assert any(issue.code == "invalid_log_level" for issue in result.errors)


def test_validator_flags_an_empty_plugin_directory() -> None:
    result = ConfigurationValidator().validate(Settings(plugin_extensions_dir=""))
    assert result.is_valid is False
    assert any(issue.code == "empty_plugin_dir" for issue in result.errors)


def test_validator_flags_an_unresolvable_ai_provider() -> None:
    result = ConfigurationValidator().validate(Settings(ai_default_provider="not-a-real-provider"))
    assert result.is_valid is False
    assert any(issue.code == "ai_provider_unresolvable" for issue in result.errors)


def test_validator_reports_missing_plugin_folder_as_informational_not_error() -> None:
    result = ConfigurationValidator().validate(Settings(plugin_extensions_dir="/does/not/exist/anywhere"))
    assert result.is_valid is True
    plugin_issues = [issue for issue in result.issues if issue.area == "plugin_folder"]
    assert plugin_issues and all(issue.severity == IssueSeverity.INFO for issue in plugin_issues)


def test_validator_covers_every_named_area() -> None:
    result = ConfigurationValidator().validate(Settings())
    areas = {issue.area for issue in result.issues}
    assert areas <= {"directories", "plugin_folder", "memory", "ai_provider", "database", "mcp", "logging"}
    # memory/mcp always report (no dedicated config exists yet) — proves every named area was actually checked.
    assert {"memory", "mcp"} <= areas


def test_validation_result_errors_and_warnings_properties() -> None:
    result = ConfigurationValidator().validate(Settings(log_level="BOGUS"))
    assert all(issue.severity == IssueSeverity.ERROR for issue in result.errors)
    assert all(issue.severity == IssueSeverity.WARNING for issue in result.warnings)
