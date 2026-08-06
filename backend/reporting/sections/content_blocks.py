"""Content blocks: the renderable units every ``ReportSection`` is made of.

A discriminated union, not one loose catch-all model — each block type has
a genuinely different shape (a paragraph is text, a table is headers/rows,
a KPI grid is name/value pairs), unlike ``ChartSpecification`` where every
chart type shares one uniform ``ChartSeries`` shape. ``KPIGridBlock``
embeds actual KPI values directly (small, already plain data — self-
contained is nearly free), while ``ChartReferenceBlock`` stays a
lightweight reference (``chart_id``/``title``/``chart_type`` only) since a
chart's full series data is large and rendering it is
``backend.visualization``'s job, not this package's.
"""

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class ContentBlockType(str, Enum):
    """Every content block type the reporting framework supports."""

    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    TABLE = "table"
    KPI_GRID = "kpi_grid"
    CHART_REFERENCE = "chart_reference"
    IMAGE_PLACEHOLDER = "image_placeholder"
    CODE_BLOCK_PLACEHOLDER = "code_block_placeholder"


class ParagraphBlock(BaseModel):
    """A block of plain narrative text."""

    block_type: Literal[ContentBlockType.PARAGRAPH] = ContentBlockType.PARAGRAPH
    text: str


class BulletListBlock(BaseModel):
    """An unordered list of short items."""

    block_type: Literal[ContentBlockType.BULLET_LIST] = ContentBlockType.BULLET_LIST
    items: list[str] = Field(default_factory=list)


class TableBlock(BaseModel):
    """A self-contained data table — headers and rows embedded directly."""

    block_type: Literal[ContentBlockType.TABLE] = ContentBlockType.TABLE
    headers: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    caption: str | None = None


class ReportKPIEntry(BaseModel):
    """One KPI's name and value, embedded directly (not a reference)."""

    name: str
    value: float | int | None = None
    kpi_type: str | None = None


class KPIGridBlock(BaseModel):
    """A grid of KPI values, self-contained for direct rendering."""

    block_type: Literal[ContentBlockType.KPI_GRID] = ContentBlockType.KPI_GRID
    kpis: list[ReportKPIEntry] = Field(default_factory=list)
    columns: int = 4


class ChartReferenceBlock(BaseModel):
    """A lightweight reference to a chart described elsewhere (``VisualizationResult``).

    Deliberately does not embed the chart's series data — rendering a
    chart is ``backend.visualization``'s job; this only notes that one
    belongs here, for a future PDF/PPT exporter to resolve.
    """

    block_type: Literal[ContentBlockType.CHART_REFERENCE] = ContentBlockType.CHART_REFERENCE
    chart_id: str
    title: str
    chart_type: str
    caption: str | None = None


class ImagePlaceholderBlock(BaseModel):
    """An explicit "no image yet" placeholder — not implemented in this phase."""

    block_type: Literal[ContentBlockType.IMAGE_PLACEHOLDER] = ContentBlockType.IMAGE_PLACEHOLDER
    caption: str
    alt_text: str | None = None


class CodeBlockPlaceholderBlock(BaseModel):
    """An explicit "no code content yet" placeholder — not implemented in this phase."""

    block_type: Literal[ContentBlockType.CODE_BLOCK_PLACEHOLDER] = ContentBlockType.CODE_BLOCK_PLACEHOLDER
    language: str | None = None
    placeholder_text: str = "Code block content is not available in this phase."


ContentBlock = Annotated[
    ParagraphBlock
    | BulletListBlock
    | TableBlock
    | KPIGridBlock
    | ChartReferenceBlock
    | ImagePlaceholderBlock
    | CodeBlockPlaceholderBlock,
    Field(discriminator="block_type"),
]
