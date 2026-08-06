"""Markdown export for a ReportDocument.

Renders every content block type into plain, GitHub-flavored Markdown. A
``ChartReferenceBlock`` becomes a labeled note (Markdown can't render a
live Plotly figure) — resolving it into an actual embedded chart is a
future PDF/PPT exporter's job, not this one's.
"""

from backend.reporting.models.report_document import ReportDocument
from backend.reporting.sections.content_blocks import (
    BulletListBlock,
    ChartReferenceBlock,
    CodeBlockPlaceholderBlock,
    ContentBlock,
    ImagePlaceholderBlock,
    KPIGridBlock,
    ParagraphBlock,
    TableBlock,
)
from backend.reporting.sections.section import ReportSection


class MarkdownReportExporter:
    """Renders a ReportDocument as a single Markdown string."""

    def export(self, document: ReportDocument) -> str:
        """Return ``document`` rendered as Markdown: header, table of contents, sections, appendices."""
        parts = [self._render_header(document), self._render_table_of_contents(document)]
        parts.extend(self._render_section(section) for section in document.sections)
        if document.appendices:
            parts.append("## Appendices\n")
            parts.extend(self._render_section(section, heading_level=3) for section in document.appendices)
        return "\n".join(parts)

    def _render_header(self, document: ReportDocument) -> str:
        lines = [f"# {document.title}"]
        if document.subtitle:
            lines.append(f"*{document.subtitle}*")
        lines.append("")
        lines.append(f"**Generated:** {document.generated_at.strftime('%Y-%m-%d %H:%M:%S')}  ")
        if document.author:
            lines.append(f"**Author:** {document.author}  ")
        lines.append(f"**Version:** {document.version}  ")
        lines.append(f"**Theme:** {document.theme}")
        lines.append("")
        return "\n".join(lines)

    def _render_table_of_contents(self, document: ReportDocument) -> str:
        if not document.table_of_contents:
            return ""
        lines = ["## Table of Contents", ""]
        lines.extend(f"{entry.order + 1}. {entry.title}" for entry in document.table_of_contents)
        lines.append("")
        return "\n".join(lines)

    def _render_section(self, section: ReportSection, heading_level: int = 2) -> str:
        heading = "#" * heading_level
        lines = [f"{heading} {section.title}", ""]
        lines.extend(self._render_block(block) for block in section.content_blocks)
        if section.notes:
            lines.append("**Notes:**")
            lines.extend(f"- {note}" for note in section.notes)
            lines.append("")
        return "\n".join(lines)

    def _render_block(self, block: ContentBlock) -> str:
        match block:
            case ParagraphBlock():
                return self._render_paragraph(block)
            case BulletListBlock():
                return self._render_bullet_list(block)
            case TableBlock():
                return self._render_table(block)
            case KPIGridBlock():
                return self._render_kpi_grid(block)
            case ChartReferenceBlock():
                return self._render_chart_reference(block)
            case ImagePlaceholderBlock():
                return self._render_image_placeholder(block)
            case CodeBlockPlaceholderBlock():
                return self._render_code_block_placeholder(block)

    def _render_paragraph(self, block: ParagraphBlock) -> str:
        return f"{block.text}\n"

    def _render_bullet_list(self, block: BulletListBlock) -> str:
        return "\n".join(f"- {item}" for item in block.items) + "\n"

    def _render_table(self, block: TableBlock) -> str:
        if not block.headers:
            return ""
        lines = []
        if block.caption:
            lines.append(f"**{block.caption}**")
        lines.append(f"| {' | '.join(block.headers)} |")
        lines.append(f"|{'|'.join(['---'] * len(block.headers))}|")
        lines.extend(f"| {' | '.join(str(cell) for cell in row)} |" for row in block.rows)
        lines.append("")
        return "\n".join(lines)

    def _render_kpi_grid(self, block: KPIGridBlock) -> str:
        lines = ["| KPI | Value |", "|---|---|"]
        lines.extend(f"| {kpi.name} | {kpi.value} |" for kpi in block.kpis)
        lines.append("")
        return "\n".join(lines)

    def _render_chart_reference(self, block: ChartReferenceBlock) -> str:
        caption = f" — {block.caption}" if block.caption else ""
        return f"> **Chart: {block.title}** ({block.chart_type}){caption}\n"

    def _render_image_placeholder(self, block: ImagePlaceholderBlock) -> str:
        return f"*[Image placeholder: {block.caption}]*\n"

    def _render_code_block_placeholder(self, block: CodeBlockPlaceholderBlock) -> str:
        language = block.language or ""
        return f"```{language}\n{block.placeholder_text}\n```\n"
