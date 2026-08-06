"""Built-in report themes plus a registry for future custom themes.

Mirrors ``backend.visualization.themes.registry.ThemeRegistry`` exactly.
"""

from backend.reporting.exceptions.errors import UnknownReportThemeError
from backend.reporting.models.theme import ReportTheme

_CORPORATE = ReportTheme(
    name="corporate",
    primary_color="#0b3d91",
    secondary_color="#1f6feb",
    background_color="#f7f9fb",
    font_family="Georgia, 'Times New Roman', serif",
    accent_palette=["#0b3d91", "#1f6feb", "#2ea043", "#c9302c", "#6c757d"],
)

_MODERN = ReportTheme(
    name="modern",
    primary_color="#4c78a8",
    secondary_color="#72b7b2",
    background_color="#ffffff",
    font_family="'Helvetica Neue', Arial, sans-serif",
    accent_palette=["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2"],
)

_MINIMAL = ReportTheme(
    name="minimal",
    primary_color="#1a1a1a",
    secondary_color="#6c757d",
    background_color="#ffffff",
    font_family="'Inter', Helvetica, sans-serif",
    accent_palette=["#1a1a1a", "#6c757d", "#adb5bd"],
)

_DARK = ReportTheme(
    name="dark",
    primary_color="#8ab4f8",
    secondary_color="#fdd663",
    background_color="#1e1e1e",
    font_family="'Segoe UI', Roboto, sans-serif",
    accent_palette=["#8ab4f8", "#fdd663", "#81c995", "#f28b82", "#78d9ec"],
)

_DEFAULT_THEMES: dict[str, ReportTheme] = {
    "corporate": _CORPORATE,
    "modern": _MODERN,
    "minimal": _MINIMAL,
    "dark": _DARK,
}


class ReportThemeRegistry:
    """Resolves a theme name to a ``ReportTheme``. Future custom themes plug in via ``register()``."""

    def __init__(self) -> None:
        self._themes: dict[str, ReportTheme] = dict(_DEFAULT_THEMES)

    def register(self, theme: ReportTheme) -> None:
        """Register (or override) a theme by name — how future custom themes plug in."""
        self._themes[theme.name] = theme

    def get(self, name: str) -> ReportTheme:
        """Return the theme registered under ``name``. Raises ``UnknownReportThemeError`` if unknown."""
        theme = self._themes.get(name)
        if theme is None:
            raise UnknownReportThemeError(f"Unknown report theme: '{name}'.")
        return theme

    def list_names(self) -> list[str]:
        """Return every registered theme name."""
        return sorted(self._themes)
