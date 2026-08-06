"""Tests for ReportDocument and TableOfContentsEntry."""

import json
from datetime import UTC, datetime

from backend.reporting.models.report_document import (
    ReportDocument,
    ReportExportFormat,
    TableOfContentsEntry,
)
from backend.reporting.sections.content_blocks import ParagraphBlock
from backend.reporting.sections.section import ReportSection, ReportSectionKind


def _make_document() -> ReportDocument:
    overview = ReportSection(
        section_id=ReportSectionKind.OVERVIEW.value,
        title="Overview",
        order=0,
        content_blocks=[ParagraphBlock(text="This report covers Q1 sales.")],
    )
    appendix = ReportSection(
        section_id=ReportSectionKind.APPENDIX.value,
        title="Appendix",
        order=0,
        content_blocks=[ParagraphBlock(text="Sample rows omitted for brevity.")],
    )
    return ReportDocument(
        report_id="report-1",
        title="Q1 Sales Report",
        subtitle="Prepared for leadership review",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        author="InsightPilot",
        theme="corporate",
        table_of_contents=[TableOfContentsEntry(section_id=overview.section_id, title=overview.title, order=0)],
        sections=[overview],
        appendices=[appendix],
        metadata={"template_type": "business_report", "dataset_id": "ds-1"},
    )


def test_document_defaults_version_and_theme() -> None:
    document = _make_document()
    assert document.version == "1.0"
    assert document.theme == "corporate"


def test_document_sections_and_appendices_are_kept_separate() -> None:
    document = _make_document()
    assert [s.section_id for s in document.sections] == [ReportSectionKind.OVERVIEW.value]
    assert [s.section_id for s in document.appendices] == [ReportSectionKind.APPENDIX.value]


def test_document_round_trips_through_json_with_no_data_loss() -> None:
    document = _make_document()

    raw = document.model_dump_json()
    restored = ReportDocument.model_validate(json.loads(raw))

    assert restored == document


def test_export_format_enum_has_all_five_formats() -> None:
    assert {fmt.value for fmt in ReportExportFormat} == {"json", "markdown", "pdf", "word", "powerpoint"}
