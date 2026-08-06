"""Report theme model: style tokens a future exporter applies when rendering a document.

Mirrors ``backend.visualization.models.theme.Theme`` exactly — a plain
named set of style tokens, resolved by name through a registry
(``backend.reporting.themes.registry.ReportThemeRegistry``), never an
enum. A ``ReportDocument`` never carries color/style information itself.
"""

from pydantic import BaseModel, Field


class ReportTheme(BaseModel):
    """A named set of style tokens for report presentation."""

    name: str
    primary_color: str
    secondary_color: str
    background_color: str
    font_family: str
    accent_palette: list[str] = Field(default_factory=list)
