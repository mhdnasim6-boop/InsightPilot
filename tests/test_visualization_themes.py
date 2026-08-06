"""Tests for ThemeRegistry: built-in themes plus the register() extensibility hook."""

import pytest

from backend.visualization.exceptions.errors import UnknownThemeError
from backend.visualization.models.theme import Theme
from backend.visualization.themes.registry import ThemeRegistry


def test_built_in_themes_are_registered() -> None:
    registry = ThemeRegistry()
    assert set(registry.list_names()) == {"light", "dark", "corporate"}


def test_get_returns_the_requested_theme() -> None:
    theme = ThemeRegistry().get("dark")
    assert theme.name == "dark"
    assert theme.color_palette


def test_get_raises_for_an_unknown_theme() -> None:
    with pytest.raises(UnknownThemeError):
        ThemeRegistry().get("neon")


def test_register_adds_a_custom_theme_without_touching_the_registry_class() -> None:
    registry = ThemeRegistry()
    custom = Theme(name="high_contrast", background_color="#000", font_color="#fff", grid_color="#333")

    registry.register(custom)

    assert registry.get("high_contrast") is custom
    assert "high_contrast" in registry.list_names()


def test_register_can_override_a_built_in_theme() -> None:
    registry = ThemeRegistry()
    replacement = Theme(name="light", background_color="#f0f0f0", font_color="#111", grid_color="#ccc")

    registry.register(replacement)

    assert registry.get("light").background_color == "#f0f0f0"
