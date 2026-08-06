"""Tests for FeatureFlagService: a read-only view over Settings' own *_enabled fields."""

import pytest

from backend.operations.exceptions import UnknownFeatureFlagError
from backend.operations.feature_flags.feature_flag import FeatureFlagName
from backend.operations.feature_flags.feature_flag_service import FeatureFlagService
from config.settings import Settings


def test_list_flags_returns_every_flag_name() -> None:
    service = FeatureFlagService(Settings())
    names = {flag.name for flag in service.list_flags()}
    assert names == set(FeatureFlagName)


def test_every_flag_defaults_to_enabled() -> None:
    service = FeatureFlagService(Settings())
    assert all(flag.enabled for flag in service.list_flags())


def test_is_enabled_reflects_settings() -> None:
    service = FeatureFlagService(Settings(mcp_enabled=False))
    assert service.is_enabled(FeatureFlagName.MCP_ENABLED) is False
    assert service.is_enabled(FeatureFlagName.MEMORY_ENABLED) is True


def test_get_returns_the_named_flag() -> None:
    service = FeatureFlagService(Settings(reflection_enabled=False))
    flag = service.get(FeatureFlagName.REFLECTION_ENABLED)
    assert flag.enabled is False
    assert flag.description


def test_get_raises_for_an_unrecognized_name() -> None:
    service = FeatureFlagService(Settings())
    with pytest.raises(UnknownFeatureFlagError):
        service.get("not_a_real_flag")  # type: ignore[arg-type]


def test_every_flag_has_a_non_empty_description() -> None:
    service = FeatureFlagService(Settings())
    assert all(flag.description for flag in service.list_flags())
