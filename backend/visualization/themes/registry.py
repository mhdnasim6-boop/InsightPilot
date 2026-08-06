"""Built-in themes plus a registry for future custom themes."""

from backend.visualization.exceptions.errors import UnknownThemeError
from backend.visualization.models.theme import Theme

_LIGHT = Theme(
    name="light",
    background_color="#ffffff",
    font_color="#1a1a1a",
    grid_color="#e0e0e0",
    color_palette=["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#EECA3B"],
)

_DARK = Theme(
    name="dark",
    background_color="#1e1e1e",
    font_color="#f5f5f5",
    grid_color="#3a3a3a",
    color_palette=["#8ab4f8", "#fdd663", "#81c995", "#f28b82", "#78d9ec", "#d7aefb"],
)

_CORPORATE = Theme(
    name="corporate",
    background_color="#f7f9fb",
    font_color="#0b1f33",
    grid_color="#d5dce3",
    color_palette=["#0b3d91", "#1f6feb", "#2ea043", "#c9302c", "#6c757d", "#f0ad4e"],
)

_DEFAULT_THEMES: dict[str, Theme] = {"light": _LIGHT, "dark": _DARK, "corporate": _CORPORATE}


class ThemeRegistry:
    """Resolves a theme name to a ``Theme``. Future custom themes plug in via ``register()``."""

    def __init__(self) -> None:
        self._themes: dict[str, Theme] = dict(_DEFAULT_THEMES)

    def register(self, theme: Theme) -> None:
        """Register (or override) a theme by name — how future custom themes plug in."""
        self._themes[theme.name] = theme

    def get(self, name: str) -> Theme:
        """Return the theme registered under ``name``. Raises ``UnknownThemeError`` if unknown."""
        theme = self._themes.get(name)
        if theme is None:
            raise UnknownThemeError(f"Unknown theme: '{name}'.")
        return theme

    def list_names(self) -> list[str]:
        """Return every registered theme name."""
        return sorted(self._themes)
