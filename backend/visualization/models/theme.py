"""Theme models: style tokens an exporter applies when rendering a chart.

Themes affect rendering only — a ``ChartSpecification`` never carries
color/style information itself.
"""

from pydantic import BaseModel, Field


class Theme(BaseModel):
    """A named set of style tokens (colors, palette) for chart rendering."""

    name: str
    background_color: str
    font_color: str
    grid_color: str
    color_palette: list[str] = Field(default_factory=list)
