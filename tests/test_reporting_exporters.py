"""Tests for the report exporters: JSON, Markdown, and the PDF/Word/PowerPoint placeholders."""

import json
from datetime import UTC, datetime

from backend.reporting.exporters.json_exporter import JSONReportExporter
from backend.reporting.exporters.markdown_exporter import MarkdownReportExporter
from backend.reporting.exporters.placeholders import (
    PDFReportExporter,
    PowerPointReportExporter,
    WordReportExporter,
)
from backend.reporting.models.report_document import (
    ReportDocument,
    TableOfContentsEntry,
)
from backend.reporting.sections.content_blocks import (
    BulletListBlock,
    ChartReferenceBlock,
    CodeBlockPlaceholderBlock,
    ImagePlaceholderBlock,
    KPIGridBlock,
    ParagraphBlock,
    ReportKPIEntry,
    TableBlock,
)
from backend.reporting.sections.section import ReportSection
from backend.visualization.models.placeholder import ExportPlaceholder


def _make_document() -> ReportDocument:
    overview = ReportSection(
        section_id="overview",
        title="Overview",
        order=0,
        content_blocks=[
            ParagraphBlock(text="This report covers Q1 sales."),
            BulletListBlock(items=["Revenue up 12%", "Costs flat"]),
        ],
    )
    kpis = ReportSection(
        section_id="kpis",
        title="KPIs",
        order=1,
        content_blocks=[KPIGridBlock(kpis=[ReportKPIEntry(name="Total Revenue", value=3690, kpi_type="sum")])],
    )
    charts = ReportSection(
        section_id="charts",
        title="Charts",
        order=2,
        content_blocks=[
            ChartReferenceBlock(chart_id="c1", title="Revenue Trend", chart_type="line", caption="Monthly revenue")
        ],
        charts=["c1"],
        notes=["Chart rendering happens client-side."],
    )
    appendix = ReportSection(
        section_id="appendix",
        title="Appendix",
        order=0,
        content_blocks=[
            TableBlock(headers=["Region", "Revenue"], rows=[["East", 1000], ["West", 200]], caption="Sample rows"),
            ImagePlaceholderBlock(caption="Revenue chart snapshot"),
            CodeBlockPlaceholderBlock(language="python"),
        ],
        tables=["Sample rows"],
    )
    return ReportDocument(
        report_id="report-1",
        title="Q1 Sales Report",
        subtitle="Prepared for leadership",
        generated_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        author="InsightPilot",
        theme="corporate",
        table_of_contents=[
            TableOfContentsEntry(section_id="overview", title="Overview", order=0),
            TableOfContentsEntry(section_id="kpis", title="KPIs", order=1),
            TableOfContentsEntry(section_id="charts", title="Charts", order=2),
            TableOfContentsEntry(section_id="appendix", title="Appendix", order=3),
        ],
        sections=[overview, kpis, charts],
        appendices=[appendix],
        metadata={"template_type": "business_report", "dataset_id": "ds-1"},
    )


# -- JSON -----------------------------------------------------------------------


def test_json_exporter_produces_valid_json() -> None:
    content = JSONReportExporter().export(_make_document())
    parsed = json.loads(content)
    assert parsed["report_id"] == "report-1"
    assert parsed["sections"][1]["content_blocks"][0]["block_type"] == "kpi_grid"


def test_json_exporter_round_trips_without_data_loss() -> None:
    document = _make_document()
    content = JSONReportExporter().export(document)
    restored = ReportDocument.model_validate_json(content)
    assert restored == document


# -- Markdown ---------------------------------------------------------------------


def test_markdown_exporter_renders_title_and_metadata() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert markdown.startswith("# Q1 Sales Report")
    assert "*Prepared for leadership*" in markdown
    assert "**Author:** InsightPilot" in markdown


def test_markdown_exporter_renders_table_of_contents() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "## Table of Contents" in markdown
    assert "1. Overview" in markdown
    assert "4. Appendix" in markdown


def test_markdown_exporter_renders_every_section_heading() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "## Overview" in markdown
    assert "## KPIs" in markdown
    assert "## Charts" in markdown
    assert "## Appendices" in markdown
    assert "### Appendix" in markdown  # nested one level deeper than top-level sections


def test_markdown_exporter_renders_kpi_grid_as_a_table() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "| Total Revenue | 3690 |" in markdown


def test_markdown_exporter_renders_chart_reference_as_a_blockquote() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "> **Chart: Revenue Trend** (line) — Monthly revenue" in markdown


def test_markdown_exporter_renders_bullet_list_items() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "- Revenue up 12%" in markdown
    assert "- Costs flat" in markdown


def test_markdown_exporter_renders_data_table_with_caption() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "**Sample rows**" in markdown
    assert "| Region | Revenue |" in markdown
    assert "| East | 1000 |" in markdown


def test_markdown_exporter_renders_image_and_code_placeholders() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "*[Image placeholder: Revenue chart snapshot]*" in markdown
    assert "```python" in markdown


def test_markdown_exporter_renders_section_notes() -> None:
    markdown = MarkdownReportExporter().export(_make_document())
    assert "**Notes:**" in markdown
    assert "- Chart rendering happens client-side." in markdown


# -- Placeholders -------------------------------------------------------------------


def test_pdf_exporter_returns_an_honest_placeholder() -> None:
    result = PDFReportExporter().export(_make_document())
    assert isinstance(result, ExportPlaceholder)
    assert result.implemented is False
    assert result.format == "pdf"
    assert result.note


def test_word_exporter_returns_an_honest_placeholder() -> None:
    result = WordReportExporter().export(_make_document())
    assert isinstance(result, ExportPlaceholder)
    assert result.format == "word"
    assert result.implemented is False


def test_powerpoint_exporter_returns_an_honest_placeholder() -> None:
    result = PowerPointReportExporter().export(_make_document())
    assert isinstance(result, ExportPlaceholder)
    assert result.format == "powerpoint"
    assert result.implemented is False
