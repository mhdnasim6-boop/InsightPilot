"""Tests for the ContentBlock discriminated union and ReportSection.

Locks in, as automated tests, what was verified empirically while
building this phase: each of the 7 block types constructs with its
discriminator defaulted, a mixed list of block types round-trips through
JSON without losing type identity, and ``ReportSection`` (itself using
the union as a field type) does the same.
"""

import json

from backend.reporting.sections.content_blocks import (
    BulletListBlock,
    ChartReferenceBlock,
    CodeBlockPlaceholderBlock,
    ContentBlockType,
    ImagePlaceholderBlock,
    KPIGridBlock,
    ParagraphBlock,
    ReportKPIEntry,
    TableBlock,
)
from backend.reporting.sections.section import ReportSection, ReportSectionKind


def test_paragraph_block_defaults_its_discriminator() -> None:
    block = ParagraphBlock(text="Revenue grew steadily.")
    assert block.block_type == ContentBlockType.PARAGRAPH


def test_bullet_list_block_defaults_its_discriminator() -> None:
    block = BulletListBlock(items=["Revenue up", "Costs down"])
    assert block.block_type == ContentBlockType.BULLET_LIST
    assert block.items == ["Revenue up", "Costs down"]


def test_table_block_holds_headers_and_rows() -> None:
    block = TableBlock(headers=["Region", "Revenue"], rows=[["East", 100], ["West", 200]], caption="By region")
    assert block.block_type == ContentBlockType.TABLE
    assert block.rows[1] == ["West", 200]


def test_kpi_grid_block_embeds_kpi_values_directly() -> None:
    block = KPIGridBlock(kpis=[ReportKPIEntry(name="Total Revenue", value=1234.5, kpi_type="sum")])
    assert block.block_type == ContentBlockType.KPI_GRID
    assert block.kpis[0].value == 1234.5
    assert block.columns == 4


def test_chart_reference_block_is_a_lightweight_pointer_not_series_data() -> None:
    block = ChartReferenceBlock(chart_id="chart-1", title="Revenue Over Time", chart_type="line")
    assert block.block_type == ContentBlockType.CHART_REFERENCE
    assert not hasattr(block, "series")


def test_image_placeholder_block_requires_a_caption() -> None:
    block = ImagePlaceholderBlock(caption="Revenue chart snapshot")
    assert block.block_type == ContentBlockType.IMAGE_PLACEHOLDER
    assert block.alt_text is None


def test_code_block_placeholder_has_a_default_placeholder_text() -> None:
    block = CodeBlockPlaceholderBlock()
    assert block.block_type == ContentBlockType.CODE_BLOCK_PLACEHOLDER
    assert block.placeholder_text


def test_section_with_every_block_type_round_trips_through_json() -> None:
    section = ReportSection(
        section_id=ReportSectionKind.OVERVIEW.value,
        title="Overview",
        order=0,
        content_blocks=[
            ParagraphBlock(text="Summary text."),
            BulletListBlock(items=["a", "b"]),
            TableBlock(headers=["x"], rows=[[1]]),
            KPIGridBlock(kpis=[ReportKPIEntry(name="Revenue", value=10)]),
            ChartReferenceBlock(chart_id="c1", title="Chart", chart_type="bar"),
            ImagePlaceholderBlock(caption="cap"),
            CodeBlockPlaceholderBlock(),
        ],
    )

    raw = section.model_dump_json()
    restored = ReportSection.model_validate(json.loads(raw))

    assert [block.block_type for block in restored.content_blocks] == [
        block.block_type for block in section.content_blocks
    ]
    assert isinstance(restored.content_blocks[0], ParagraphBlock)
    assert isinstance(restored.content_blocks[3], KPIGridBlock)
    assert isinstance(restored.content_blocks[4], ChartReferenceBlock)
