"""Tests for ReportThemeRegistry."""

import pytest

from backend.reporting.exceptions.errors import UnknownReportThemeError
from backend.reporting.models.theme import ReportTheme
from backend.reporting.themes.registry import ReportThemeRegistry


def test_list_names_returns_all_four_built_in_themes() -> None:
    registry = ReportThemeRegistry()
    assert registry.list_names() == ["corporate", "dark", "minimal", "modern"]


@pytest.mark.parametrize("name", ["corporate", "modern", "minimal", "dark"])
def test_get_resolves_each_built_in_theme_by_name(name: str) -> None:
    theme = ReportThemeRegistry().get(name)
    assert theme.name == name
    assert theme.primary_color
    assert theme.font_family


def test_get_raises_for_an_unregistered_theme_name() -> None:
    with pytest.raises(UnknownReportThemeError):
        ReportThemeRegistry().get("nonexistent")


def test_register_adds_a_custom_theme() -> None:
    registry = ReportThemeRegistry()
    custom = ReportTheme(
        name="high_contrast",
        primary_color="#000000",
        secondary_color="#ffffff",
        background_color="#ffffff",
        font_family="Arial",
    )

    registry.register(custom)

    assert registry.get("high_contrast") == custom
    assert "high_contrast" in registry.list_names()


def test_register_overrides_a_built_in_theme_by_name() -> None:
    registry = ReportThemeRegistry()
    replacement = ReportTheme(
        name="corporate",
        primary_color="#111111",
        secondary_color="#222222",
        background_color="#ffffff",
        font_family="Verdana",
    )

    registry.register(replacement)

    assert registry.get("corporate").primary_color == "#111111"


def test_registries_are_independent_instances() -> None:
    registry_a = ReportThemeRegistry()
    registry_b = ReportThemeRegistry()

    registry_a.register(
        ReportTheme(
            name="only_in_a", primary_color="#000", secondary_color="#111", background_color="#fff", font_family="x"
        )
    )

    assert "only_in_a" in registry_a.list_names()
    assert "only_in_a" not in registry_b.list_names()
